import os
# os.environ["OLLAMA_HOST"] = "http://ollamaProjet4A:11434"
from typing import List, Dict
import argparse

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

DB_NAME = "test"
DB_USER = "postgres"
DB_PASSWORD = "Admin"
DB_HOST = "localhost"

# --- CONSTantes de connexion PostgreSQL
DB_URI = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}"
engine = create_engine(DB_URI, echo=False)

MEMORY_COLLECTION = "memories"
DOCS_COLLECTION = "knowledge_base"

# --- Module d'embeddings (Sentence-Transformers)
ollama_embeddings = OllamaEmbeddings(
    model="granite3.1-dense:8b"
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

MODEL_NAME = "granite3.1-dense:8b"

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
        chunk_size=100000,
        chunk_overlap=150,
        length_function=len,
        is_separator_regex=False,
    )
    llm_ctx = OllamaLLM(model=MODEL_NAME)

    chunks_out: List[Document] = []

    for src, pages in grouped.items():
        full_text = "\n\n".join(p.page_content for p in pages)[:200000]  # cap prompt length
        virtual_doc = Document(page_content=full_text, metadata={"source": src, "page": 0})
        raw_chunks = splitter.split_documents([virtual_doc])
        raw_chunks = calculate_chunk_ids(raw_chunks)

        print(f"Processing {src} – {len(raw_chunks)} chunks")
        for ch in tqdm(raw_chunks, leave=False):
            cid = ch.metadata["id"]
            if cid in existing_ids:
                chunks_out.append(ch)  # already contextualised previously
                continue

            prompt = (
                f"<RAG>\n{full_text}\n</RAG>\n"
                f"<chunk>\n{ch.page_content}\n</chunk>\n"
                "Please provide a short, succinct sentence that situates the chunk "
                "within the overall RAG to improve search retrieval. Answer in French, "
                "without additional commentary."
            )
            ctx_sentence = llm_ctx.invoke(prompt).strip()
            ch.page_content = f"{ctx_sentence}\n###\n{ch.page_content}"
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
        [content],
        metadatas=[{"message_id": message_id, "conversation_id": conversation_id}],
    )
    return message_id


def retrieve_memories(conversation_id: int, query: str, k: int = 5) -> List[str]:
    retriever = auth_memory_store.as_retriever(
        search_kwargs={"k": k, "filter": {"conversation_id": conversation_id}}
    )
    return [d.page_content for d in retriever.invoke(query)]


def retrieve_documents(query: str, k: int = 4) -> List[str]:
    retriever = kb_store.as_retriever(search_kwargs={"k": k})
    return [d.page_content for d in retriever.invoke(query)]

def search_if_relevant(user_input: str, doc_passages: List[str]) -> bool:
    if not doc_passages:
        return "no"
    
    llm = OllamaLLM(model=MODEL_NAME)
    prompt = (
        "If the user input is mentionning any documents, he is not talking about the RAG but the documents he uploaded.\n"
        "Here, given the user input and BASED ON USER INPUTS compared to the RAG, determine if the input is relevant and has a CLEAR LINK to the content IN THE RAG.\n\n"
        "The RAG is ONLY RELEVANT FOR UPHF related questions, not for non-UPHF related questions.\n"
        f"User Input: {user_input}\n\n"
        "RAG:\n" + "\n".join(doc_passages) + "\n\n"
        "Is the user input content relevant to the RAG? Answer ONLY with 'yes' and add the following tag in the answer #yes#"
    )
    response = llm.invoke(prompt)
    response = response.strip().lower()
    print(response)
    
    return response

def answer_with_memory(user_input: str, conversation_id: int, k_mem: int = 5, k_docs: int = 5, files_names: List[str] = []) -> str:
    """Full round‑trip: store Q → retrieve memories + docs → build prompt → LLM."""
    mem_passages = retrieve_memories(conversation_id, user_input, k=k_mem)
    doc_passages = retrieve_documents(user_input, k=k_docs)
    
    if files_names:
        user_input += f"The files the user is talking about are : " + ", ".join(files_names)

    relevant = search_if_relevant(user_input, doc_passages)
    
    def fmt(passages: List[str], label: str) -> str:
        if not passages:
            return f"Aucun {label} pertinent trouvé."
        return "\n".join(f"{label} {i+1}: {txt}" for i, txt in enumerate(passages))

    # context_block = "\n\n".join(
    #     [fmt(mem_passages, "mémoire"), fmt(doc_passages, "document")]
    # )

    system_msg = {
    "role": "system",
    "content": """
    You are a specialized French-speaking virtual assistant named Chat-ON, designed to answer questions by using if necessary the information provided between the <conversation_context> and </conversation_context> tags.

    Rules to follow:
    - ONLY use information between the <conversation_context> and </conversation_context> tags if it is directly relevant to the question.
    - ONLY use information between the <RAG> and </RAG> tags ONLY if it is relevant to the question otherwise COMPLETELY IGNORE it.
    - Do NOT provide off-topic or unsolicited information.
    - Adapt the length of your answer to the level of detail of the question: be concise if the question is simple or vague.
    - Stay professional and clear.
    - Do NOT mention that you use the context or the memory in your answer.
    - If the question is too vague or if the user message is just random words, ask for clarification to the user.

    Examples:

    Expected behavior:
    User: Hello!
    Answer: Hello! I'm a virtual assistant in cybersecurity, at your disposal.

    Behaviour to avoid:
    User: Hello!
    Answer: Hello! I'm a virtual assistant in cybersecurity, here to answer your questions. Good cybersecurity practices include [...] (this is off-topic as not requested).

    Your priority is contextual relevance, conciseness, and clarity.
    Please answer by defaut in French, do not add the English translation unless explicitly requested.
    """
    }
    
    if "#yes#" not in relevant:
        doc_passages = []

    user_msg = {
        "role": "user",
        "content": f"""
    
    ### Conversation context :
    <conversation_context>
    {fmt(mem_passages, "mémoire")}
    </conversation_context>
    
    ---
    
    ### User prompt :
    <user_input>
    {user_input}
    </user_input>

    ---

    ### RAG – ONLY use if relevant : 
    <RAG>
    {fmt(doc_passages, "document")}
    </RAG>
    """.strip()
    }
    
    # print([system_msg, user_msg])

    response = ollama_chat(model=MODEL_NAME, messages=[system_msg, user_msg], stream=False)
    assistant_answer = response["message"]["content"]

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
