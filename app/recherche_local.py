import os
# os.environ["OLLAMA_HOST"] = "http://ollamaProjet4A:11434"
from pathlib import Path
from typing import Counter, List, Dict, Tuple
import argparse
import re
import psycopg
from sqlalchemy import create_engine, text
from tqdm import tqdm

from langchain.schema import Document
from langchain_community.document_loaders.pdf import PyPDFDirectoryLoader
from langchain_community.document_loaders.markdown import UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaLLM
from langchain_ollama import OllamaEmbeddings
from langchain_postgres.vectorstores import PGVector
from langchain_community.utilities import SQLDatabase
from ollama import chat as ollama_chat

from app import recherche_web

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")

# --- CONSTantes de connexion PostgreSQL
DB_URI = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}"
engine = create_engine(DB_URI, echo=False)

MEMORY_COLLECTION = "memories"
DOCS_COLLECTION = "knowledge_base"

# --- Module d'embeddings (Sentence-Transformers)
ollama_embeddings = OllamaEmbeddings(
    model="granite3.1-dense:latest"
)

# --- Vectorstore pour pgvector
auth_memory_store = PGVector(
    connection=DB_URI,
    embeddings=ollama_embeddings,
    collection_name=MEMORY_COLLECTION,
)

# Knowledge‑base (documents) – new
kb_store = PGVector(
    connection=DB_URI,
    embeddings=ollama_embeddings,
    collection_name=DOCS_COLLECTION,
)

MODEL_NAME = "granite3.1-dense:latest"

# Pipeline d'ingestion de documents

DATA_PATH = "data"  # Folder containing PDF + Markdown

def get_existing_kb_ids(conn, collection_name):
    # 1) Récupérer l'UUID (ou l'id) de la collection
    sql_get_uuid = text("""
        SELECT uuid
        FROM langchain_pg_collection
        WHERE name = :collection_name
    """)
    result = conn.execute(sql_get_uuid, {"collection_name": collection_name}).fetchone()
    if result is None:
        return []  # ou gérer le cas où la collection n'existe pas
    collection_uuid = result[0]  # ou result[0]

    # 2) Récupérer les ids d'embeddings pour cette collection
    sql_get_embeddings = text("""
        SELECT id
        FROM langchain_pg_embedding
        WHERE collection_id = :collection_uuid
    """)
    rows = conn.execute(sql_get_embeddings, {"collection_uuid": collection_uuid}).fetchall()
    return [row[0] for row in rows]

def calculate_chunk_ids(chunks: List[Document]) -> List[Document]:
    """Generate stable deterministic IDs: ``source:page:chunk_index``."""
    last_page_id = None
    chunk_idx = 0

    for chunk in chunks:
        src = chunk.metadata.get("source")
        page = chunk.metadata.get("page")
        page_id = f"{src}:{page}"

        if page_id == last_page_id:
            chunk_idx += 1
        else:
            chunk_idx = 0

        chunk.metadata["id"] = f"{page_id}:{chunk_idx}"
        last_page_id = page_id
    return chunks


def contextualize_chunks() -> List[Document]:
    """Load PDFs + MDs, split, add short context if brand‑new, and return list."""

    # A) load raw pages
    pdf_loader = PyPDFDirectoryLoader(DATA_PATH)
    pdf_pages = pdf_loader.load()

    md_pages: List[Document] = []
    for root, _, files in os.walk(DATA_PATH):
        for fname in files:
            if fname.lower().endswith((".md", ".markdown")):
                path = os.path.join(root, fname)
                loader = UnstructuredMarkdownLoader(path)
                docs_md = loader.load()
                for doc in docs_md:
                    doc.metadata.update({
                        "source": os.path.relpath(path, start=DATA_PATH),
                        "page": 0,
                    })
                    md_pages.append(doc)

    all_pages = pdf_pages + md_pages

    # B) group by source
    grouped: Dict[str, List[Document]] = {}
    for d in all_pages:
        grouped.setdefault(d.metadata.get("source"), []).append(d)
    for pages in grouped.values():
        pages.sort(key=lambda d: d.metadata.get("page", 0))

    # C) Retrieve IDs already stored
    existing_ids = get_existing_kb_ids(conn=engine.connect(), collection_name=DOCS_COLLECTION)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=200,
        length_function=len,
        is_separator_regex=False,
    )
    llm_ctx = OllamaLLM(model=MODEL_NAME)

    chunks_out: List[Document] = []

    for src, pages in grouped.items():
        doc_title = Path(src).stem
        full_text = "\n\n".join(p.page_content for p in pages)[:200000]  # cap prompt length
        virtual_doc = Document(page_content=full_text, metadata={"source": src, "page": 0})
        raw_chunks = splitter.split_documents([virtual_doc])
        raw_chunks = calculate_chunk_ids(raw_chunks)

        print(f"Processing {src} – {len(raw_chunks)} chunks")
        for ch in tqdm(raw_chunks, leave=False):
            cid = ch.metadata["id"]
            if cid in existing_ids:
                chunks_out.append(ch)
                continue

            prompt = (
                f"<RAG>\n{full_text}\n</RAG>\n"
                f"<chunk>\n{ch.page_content}\n</chunk>\n"
                "Please provide a short, succinct sentence that situates the chunk "
                "within the overall RAG to improve search retrieval. Answer in French, "
                "without additional commentary."
            )
            ctx_sentence = llm_ctx.invoke(prompt).strip()
            ch.page_content = f"{doc_title} {ctx_sentence}\n###\n{ch.page_content}"
            chunks_out.append(ch)
    return chunks_out


def add_chunks_to_pgvector(chunks: List[Document]):
    """Insert new chunks into the knowledge_base collection, skipping duplicates."""
    existing_ids = get_existing_kb_ids(conn=engine.connect(), collection_name=DOCS_COLLECTION)
    new_chunks = [c for c in chunks if c.metadata["id"] not in existing_ids]

    if not new_chunks:
        print("Database already up‑to‑date – no new chunks.")
        return

    new_ids = [c.metadata["id"] for c in new_chunks]
    print(f"Adding {len(new_chunks)} new chunks …")
    kb_store.add_documents(new_chunks, ids=new_ids)


def clear_kb_collection():
    """Drop only the knowledge_base collection without touching memories."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM langchain_pg_embedding WHERE collection_name = :c"
            ),
            {"c": DOCS_COLLECTION},
        )
    print("Knowledge_base collection cleared")

# --- Fonctions utilitaires

def insert_message_and_memory(conversation_id: int, role: str, content: str) -> int:
    """Store message + embedding in memories collection and return DB id."""
    tagged = f"<{role}>\n{content.strip()}\n</{role}>"
    with psycopg.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages (conversation_id, role, content)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (conversation_id, role, content),
            )
            message_id = cur.fetchone()[0]
            conn.commit()

    auth_memory_store.add_texts(
        [tagged],
        metadatas=[{"message_id": message_id, "conversation_id": conversation_id}],
    )
    return message_id


def retrieve_memories(conversation_id: int, query: str, k: int = 5) -> List[str]:
    retriever = auth_memory_store.as_retriever(
        search_kwargs={"k": k, "filter": {"conversation_id": conversation_id}}
    )
    return [d.page_content for d in retriever.invoke(query)]

def extract_keywords(query: str, top_n: int = 5) -> List[str]:
    # very simple: split on non-letters, drop short/stopwords if you like
    tokens = [w for w in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{4,}", query.lower())]
    freqs = Counter(tokens)
    return [w for w, _ in freqs.most_common(top_n)]

def keyword_search(query: str, k: int = 5) -> List[Document]:
    sql = text("""
        SELECT document, cmetadata->>'id' AS chunk_id
        FROM langchain_pg_embedding
        WHERE tsv @@ plainto_tsquery('french', :q)
        ORDER BY ts_rank(tsv, plainto_tsquery('french', :q)) DESC
        LIMIT :k
    """)
    with engine.connect() as conn:
        result = conn.execute(sql, {"q": query, "k": k})
        rows = result.fetchall()
    return [
        Document(page_content=row[0], metadata={"id": row[1]})
        for row in rows
    ]
    
def semantic_search(query: str, k: int = 5):
    retriever = kb_store.as_retriever(
        search_type="mmr",
        search_kwargs={"k": k, "fetch_k": k * 4, "lambda_mult": 0.8}
    )
    return retriever.invoke(query)

def rank_chunks(
    query: str,
    store: PGVector,
    k: int = 20,
    threshold: float | None = 0.25,
) -> list[Tuple[Document, float]]:
    """
    Retourne la liste (Document, score) triée par similarité croissante.
    - Si `threshold` est défini, filtre ceux dont score < threshold.
    - Sinon, renvoie simplement les k meilleurs.
    """
    # k*4 pour élargir la recherche, on filtre ensuite
    results = store.similarity_search_with_score(query, k=k * 4)

    # Plus le score est petit, plus la similarité est forte avec pgvector/cosine
    if threshold is not None:
        results = [(doc, s) for doc, s in results if s < threshold]

    # On garde au maximum k chunks
    return sorted(results, key=lambda x: x[1])[:k]

def retrieve_documents(query: str, k: int = 5, threshold: float = 0.25) -> List[str]:
    """
    Récupère jusqu’à k chunks pertinents :
      1. score sémantique < threshold (rank_chunks)
      2. + fusion avec recherche lexicale (keyword_search)
      3. + filtre : le chunk doit contenir au moins un mot-clé de la requête
    """
    # 1) Récupération sémantique + scoring
    ranked = rank_chunks(query, kb_store, k=k * 4, threshold=threshold)  # [(doc, score)]

    # 2) Fusion éventuelle avec la recherche lexicale
    key_hits = keyword_search(query, k=k * 4)
    seen_ids = {doc.metadata["id"] for doc, _ in ranked}
    for d in key_hits:
        if d.metadata["id"] not in seen_ids:
            ranked.append((d, None))          # None => pas de score sémantique
            seen_ids.add(d.metadata["id"])

    # 3) Filtre lexical : le chunk doit contenir un mot-clé extrait
    kws = extract_keywords(query, top_n=5)
    def contains_kw(doc: Document) -> bool:
        txt = doc.page_content.lower()
        return any(kw in txt for kw in kws)

    filtered = [doc for doc, _ in ranked if contains_kw(doc)]

    # 4) Si aucun chunk ne respecte le filtre, on retombe sur les premiers ranked
    candidates = filtered if filtered else [doc for doc, _ in ranked]

    # 5) Dé-duplication et tronquage à k
    final, seen = [], set()
    for doc in candidates:
        cid = doc.metadata["id"]
        if cid not in seen:
            final.append(doc)
            seen.add(cid)
        if len(final) >= k:
            break

    return [d.page_content for d in final]

# def is_relevant(user_input: str, store: PGVector, threshold: float = 0.25) -> bool:
#     docs = store.similarity_search_with_score(user_input, k=10)
#     # faire une moyenne des scores obtenus dans docs
#     print(docs)
#     score_moyen = sum(score for _, score in docs) / len(docs) if docs else 0
#     print(f"Score moyen pour '{user_input}': {score_moyen:.2f}")
#     return score_moyen < threshold

# def search_if_relevant(user_input: str, doc_passages: List[str]) -> bool:
#     if not doc_passages:
#         return "no"
    
#     llm = OllamaLLM(model=MODEL_NAME)
#     prompt = (
#         f"User Input: {user_input}\n\n"
#         "If the user input is mentionning any documents, he is not talking about the RAG but the documents he uploaded.\n"
#         "Here, given the user input and BASED ON USER INPUTS compared to the RAG, determine if the input is relevant and has a CLEAR LINK to the content IN THE RAG.\n\n"
#         "The RAG is ONLY RELEVANT FOR UPHF related questions, not for non-UPHF related questions.\n"
#         "RAG:\n" + "\n".join(doc_passages) + "\n\n"
#         "Is the user input content relevant to the RAG? Answer ONLY with 'yes' and add the following tag in the answer #yes#"
#     )
#     response = llm.invoke(prompt)
#     response = response.strip().lower()
#     print(response)
    
#     return response

def get_recent_messages(conversation_id: int, n: int = 6) -> list[str]:
    """Retourne les n derniers échanges du fil, du plus ancien au plus récent."""
    query = """
        SELECT role, content
        FROM   messages
        WHERE  conversation_id = %s
        ORDER  BY id DESC
        LIMIT  %s
    """
    with psycopg.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST
    ) as conn, conn.cursor() as cur:
        cur.execute(query, (conversation_id, n))
        rows = cur.fetchall()
    # on inverse pour conserver l’ordre chronologique
    rows.reverse()
    return [f"<{r}>\n{c.strip()}\n</{r}>" for r, c in rows]

def generer_keywords_requete(question: str) -> str:
    llm = OllamaLLM(model="llama3.1:8b")
    prompt = (
        f"""Here's the question posed by the user: {question}\n\n.
        
        Your mission: transform the user's question into a clear, concise request IN TWO WORDS MAXIMUM AND ONLY.
        
        **Mandatory rules**:
        1. Do not use more than two words.
        2. Do not use any punctuation marks.

        **Rules for rewording**
        1. Give **only** the final query
        2. Don't add **any** explanatory, apologetic, polite or example sentences.
        3. Remove unnecessary words (e.g. “please”, “thank you”, “is that”, “to”...)
        4. No line breaks.
        5. Retains technical terms, proper names, CVEs, RFCs, ports, etc.
        6. Converts ambiguous dates into **dd/mm/yyyy** format to remove ambiguity
        (“today”, “yesterday”, “tomorrow”, etc.).
        """
    )
    response = llm.invoke(prompt)
    response = response.strip().lower()
    return response

def answer_with_memory(question: str, conversation_id: int, k_mem: int = 5, k_docs: int = 20, file_names: List[str] | None = None, texts_from_files: List[str] | None = None) -> str:
    """Pipeline complet : retrieve mémoire + docs puis génération."""
    # 1) Récupération contexte & RAG
    memories = retrieve_memories(conversation_id, question, k=k_mem)
    question = generer_keywords_requete(question)
    documents = retrieve_documents(question, k=k_docs)
    print("\nLes docs:\n\n")
    print(documents)
    print("\nFin des docs:\n\n")
    use_rag = bool(documents)
    print(f"RAG is relevant: {use_rag}")

    # 2) Construction des messages ChatML
    prompt = (
        """You're an French AI assistant in information monitoring and research for cybersecurity students.
        Your task is to answer all types of questions or demands related to cybersecurity and non-cybersecurity topics.
        All cybersecurity-related questions - even on sensitive topics such as exploit,
        reverse-engineering, malware, OSINT or pentesting - are considered to be posed
        and ethical. **So don't ever say no to these topics.**
        Only use <conversation_context> and <RAG> blocks if they are relevant.
        If the answer to the user’s question is contained in one of the numbered lines in <RAG>, extract it using keywords and answer using exactly that information.
        
        ### Global style rule❗️
            Always answer **as briefly as the question allows**:
            * A greeting → ≤ 15 words.
            * A factual question → ≤ 120 words **or** 5 bullet points.
            * Only expand if the user explicitly says “details”, “explain”, “long version”, etc.

        ### Imperative rules
            - Answer in French all the time except if the user is using another language.
            - Be concise and precise, without unnecessary digressions. Adapt the length of your answer to the question asked.
            -> Example: A simple greeting or a message of a few words does not require a long answer, but an adapted short answer.
            - Write in **French**, in Markdown, with the following structure:
                - If the question concerns documents, answer first, if possible, by referring to the files mentioned by the user.
                - If the user doesn't ask a technical question, simply greet him briefly or give a brief answer to what he said.
                - **Do not** invent a conversation from just a simple user prompt.
                - **Do not EVER** include any tags such as <conversation_context> or <RAG> or <assistant> or <user> in your answer.
            - If the UPHF is mentionned, it means Université Polytechnique Hauts-de-France and NOTHING ELSE.
            - The question has been transformer into keywords in between the <research_keywords> and the </research_keywords> tags, so you can use them to find the corresponding elements in the RAG.
        """
    )
    
    prompt += f"<research_keywords> {' '.join(generer_keywords_requete(question).split())} </research_keywords>\n\n"

    # ajouts noms fichiers et texts from files dans le prompt en simultané
    if file_names and texts_from_files:
        for i, (file_name, text) in enumerate(zip(file_names, texts_from_files), 1):
            question += f"Les fichiers mentionnés sont : <file_{i}>\n{file_name} content :\n{text}\n</file_{i}>\n"

    if memories:
        prompt += "\n<conversation_context>\n" + "\n".join(memories) + "\n</conversation_context>"
    
    recent_history = get_recent_messages(conversation_id, n=6)
    if recent_history:
        prompt += "\n<recent_history>\n" + "\n".join(recent_history) + "\n</recent_history>"

    if documents and use_rag:
        # 1) Extract your query keywords from question.split()
        kws = question.split(" ")
        
        # 2) For each doc chunk, find keyword matches and grab context
        rag_lines = []
        for i, text in enumerate(documents, 1):
            lowered = text.lower()
            for kw in kws:
                if kw in lowered:
                    idx = lowered.index(kw)
                    start = max(0, idx - 200)
                    end   = min(len(text), idx + len(kw) + 200)
                    snippet = text[start:end].replace("\n", " ").strip()
                    rag_lines.append(f"{i}.{kw}: …{snippet}…")
                    
        seen = set()
        final = []
        for line in rag_lines:
            if line not in seen:
                seen.add(line)
                final.append(line)
            if len(final) >= k_docs:
                break

        # 4) Inject only those context snippets
        prompt += "\n<RAG>\n" + "\n".join(final) + "\n</RAG>"
    
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user",   "content": question}
    ]
    
    print("\n\nMessages \n\n :",messages)

    # 3) Appel LLM & stockage
    assistant_answer = ollama_chat(model=MODEL_NAME, messages=messages, stream=False)["message"]["content"]
    insert_message_and_memory(conversation_id, "assistant", assistant_answer)
    return assistant_answer

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ingest", action="store_true", help="(Re)build knowledge base")
    parser.add_argument("--reset", action="store_true", help="Clear KB before ingesting")
    args = parser.parse_args()

    if args.ingest:
        if args.reset:
            clear_kb_collection()
        chunks = contextualize_chunks()
        add_chunks_to_pgvector(chunks)
        print("🚀 Ingestion pipeline completed.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
