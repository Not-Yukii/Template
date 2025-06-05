import psycopg
from langchain_postgres.vectorstores import PGVector
from langchain_community.utilities import SQLDatabase
from langchain_ollama import OllamaEmbeddings
from sqlalchemy import create_engine
from ollama import chat

# --- CONSTantes de connexion PostgreSQL
DB_URI = "postgresql+psycopg://postgres:Admin@localhost:5432/test"
engine = create_engine(DB_URI, echo=False)

# --- Module d'embeddings (Sentence-Transformers)
ollama_embeddings = OllamaEmbeddings(
    model="granite3.1-dense:8b"
)

# --- Vectorstore pour pgvector
vectorstore = PGVector(
    connection=DB_URI,
    embeddings=ollama_embeddings, # objet complet
    collection_name="memories"
)

MODEL_NAME = "granite3.1-dense:8b"

# --- Fonctions utilitaires

def insert_message_and_memory(conversation_id: int, role: str, content: str) -> int:
    """
    1) Insère un message dans la table 'messages'
    2) Calcule l'embedding (hf_embeddings.embed_query)
    3) Insère dans 'memories'
    4) Retourne le message_id.
    """
    conn = psycopg.connect(
        dbname="test", user="postgres", password="Admin", host="localhost"
    )
    cursor = conn.cursor()
    # (a) Insertion dans messages
    cursor.execute(
        """
        INSERT INTO messages (conversation_id, role, content)
        VALUES (%s, %s, %s)
        RETURNING id;
        """,
        (conversation_id, role, content)
    )
    message_id = cursor.fetchone()[0]
    conn.commit()
    
    vectorstore.add_texts(
        [content],
        metadatas=[{"message_id": message_id, "conversation_id": conversation_id}],
    )

    cursor.close()
    conn.close()
    return message_id

def retrieve_memories(conversation_id: int, query: str, k: int = 5) -> list[str]:
    """
    Récupère les k passages les plus similaires DANS LA MÊME conversation.
    """
    retriever = vectorstore.as_retriever(
        search_kwargs={
            "k": k,
            "filter": {"conversation_id": conversation_id}
        }
    )
    docs = retriever.invoke(query)
    # docs est une liste d’objets Document, dont `page_content` est la colonne `content` de memories
    return [doc.page_content for doc in docs]

def answer_with_memory(user_input: str, conversation_id: int, k: int = 5) -> str:
    """
    1. Insère la question de l'utilisateur dans messages + embedding en memory.
    2. Récupère les k messages mémorisés les plus proches (questions + réponses).
    3. Construit le prompt avec ces passages et la nouvelle question.
    4. Génère la réponse via Ollama.
    5. Insère la réponse dans messages + memory.
    6. Retourne la réponse.
    """
   # (1) Insérer la question de l'utilisateur
    insert_message_and_memory(conversation_id, "user", user_input)

    # (2) Retrieval dans pgvector, limité à cette même conversation
    passages = retrieve_memories(conversation_id, user_input, k=k)
    # passages est une liste de chaînes de caractères issues de la colonne `content` de `memories`

    # (3) Construire le prompt
    if passages:
        context = "\n".join(f"Mémoire {i+1}: {txt}" for i, txt in enumerate(passages))
    else:
        context = "Aucun contexte pertinent trouvé dans cette conversation."
        
    system_msg = {
        "role": "system",
        "content": """
        Tu es un assistant intelligent français qui répond aux questions en prévilégiant les informations fournies dans le contexte.
        Si nécessaire, bases toi sur le contexte fournis pour formuler ta réponse.
        """
    }
    user_msg = {
        "role": "user",
        "content": f"{context}\n\n Voici la question : {user_input}"
    }

    # (4) Génération via Ollama
    response = chat(
        model=MODEL_NAME,
        messages=[system_msg, user_msg],
        stream=False
    )
    assistant_response = response["message"]["content"]

    # (5) Insérer la réponse dans messages + embedding
    insert_message_and_memory(conversation_id, "assistant", assistant_response)

    # (6) Retourner la réponse
    return assistant_response