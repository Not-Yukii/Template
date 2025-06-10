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
        chunk_size=1500,
        chunk_overlap=200,
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

def is_relevant(user_input: str, store: PGVector, threshold: float = 0.22) -> bool:
    docs = store.similarity_search_with_score(user_input, k=1)
    return docs and docs[0][1] < threshold

def search_if_relevant(user_input: str, doc_passages: List[str]) -> bool:
    if not doc_passages:
        return "no"
    
    llm = OllamaLLM(model=MODEL_NAME)
    prompt = (
        f"User Input: {user_input}\n\n"
        "If the user input is mentionning any documents, he is not talking about the RAG but the documents he uploaded.\n"
        "Here, given the user input and BASED ON USER INPUTS compared to the RAG, determine if the input is relevant and has a CLEAR LINK to the content IN THE RAG.\n\n"
        "The RAG is ONLY RELEVANT FOR UPHF related questions, not for non-UPHF related questions.\n"
        "RAG:\n" + "\n".join(doc_passages) + "\n\n"
        "Is the user input content relevant to the RAG? Answer ONLY with 'yes' and add the following tag in the answer #yes#"
    )
    response = llm.invoke(prompt)
    response = response.strip().lower()
    print(response)
    
    return response

def answer_with_memory(question: str, conversation_id: int, k_mem: int = 5, k_docs: int = 4, file_names: List[str] | None = None) -> str:
    """Pipeline complet : retrieve mémoire + docs puis génération."""

    # 1) Récupération contexte & RAG
    memories = retrieve_memories(conversation_id, question, k=k_mem)
    documents = retrieve_documents(question, k=k_docs)
    use_rag = is_relevant(question, kb_store)

    # 2) Construction des messages ChatML
    messages = [{
        "role": "system",
        "content": (
            "Vous êtes Chat‑ON, assistant francophone spécialiste cybersécurité. "
            "N'utilisez les blocs <conversation_context> et <RAG> que s'ils sont pertinents."),
    }]

    if file_names:
        question += " Les fichiers mentionnés sont : " + ", ".join(file_names)
    messages.append({"role": "user", "content": question})

    if memories:
        messages.append({
            "role": "system",
            "content": "<conversation_context>\n" + "\n".join(memories) + "\n</conversation_context>",
        })

    if use_rag and documents:
        rag_lines = [f"- {d.metadata['id']} · {d.page_content.split('###')[0]}" for d in documents]
        messages.append({
            "role": "system",
            "content": "<RAG>\n" + "\n".join(rag_lines) + "\n</RAG>",
        })

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
