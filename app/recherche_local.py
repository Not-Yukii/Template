import psycopg2
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import PGVector
from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine
from ollama import chat

# --- CONSTantes de connexion PostgreSQL
DB_URI = "postgresql+psycopg2://postgres:Admin@localhost:5432/test"
# On peut créer un engine SQLAlchemy que PGVector (option « connection=engine ») utilisera.
engine = create_engine(DB_URI, echo=False)

# --- Module d'embeddings (Sentence-Transformers)
hf_embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# --- Vectorstore pour pgvector
# Ici on donne l'objet hf_embeddings (pas hf_embeddings.embed_query),
# et on précise le nom logique "memories" pour la collection interne.
vectorstore = PGVector(
    connection_string=DB_URI,
    embedding_function=hf_embeddings, # objet complet
    collection_name="memories",       # nom de la collection interne
    embedding_length=384              # dimension de l'embedding
)

MODEL_NAME = "granite3.1-dense"

# --- Fonctions utilitaires

def insert_message_and_memory(conversation_id: int, role: str, content: str) -> int:
    """
    1) Insère un message dans 'messages'
    2) Récupère le message_id
    3) Calcul de l'embedding (avec hf_embeddings.embed_query)
    4) Insertion dans 'memories'
    5) Retourne message_id
    """
    conn = psycopg2.connect(
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
    # (b) Calcul de l'embedding
    embedding = hf_embeddings.embed_query(content)  # liste de floats
    # (c) Insertion dans memories
    cursor.execute(
        """
        INSERT INTO memories (message_id, content, embedding)
        VALUES (%s, %s, %s);
        """,
        (message_id, content, embedding)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return message_id


def get_conversation_history(conversation_id: int):
    """
    Récupère l'historique des messages pour une conversation donnée.
    """
    conn = psycopg2.connect(
        dbname="test", user="postgres", password="Admin", host="localhost"
    )
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT role, content, created_at
        FROM messages
        WHERE conversation_id = %s
        ORDER BY created_at;
        """,
        (conversation_id,)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows  # liste de tuples (role, content, created_at)


def answer_with_memory(user_input: str, conversation_id: int, k: int = 5) -> str:
    """
    1. Insère la question de l'utilisateur dans messages + embedding en memory.
    2. Récupère les k messages mémorisés les plus proches (questions + réponses).
    3. Construit le prompt avec ces passages et la nouvelle question.
    4. Génère la réponse via Ollama.
    5. Insère la réponse dans messages + memory.
    6. Retourne la réponse.
    """
    # (1) Insérer la question user
    user_message_id = insert_message_and_memory(conversation_id, "user", user_input)

    # (2) Retrieval dans pgvector
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})
    docs = retriever.get_relevant_documents(user_input)
    passages = [doc.page_content for doc in docs]

    # (3) Construire le prompt final
    context = "\n".join(f"Mémoire {i+1} : {txt}" for i, txt in enumerate(passages))
    system_msg = {
        "role": "system",
        "content": "Tu es un assistant expert en Python et en algorithmes."
    }
    user_msg = {
        "role": "user",
        "content": f"{context}\n\nQuestion : {user_input}\nRéponse :"
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

def recherche_local(question:str) -> str:
    reponse = answer_with_memory(question, 1, k=5)
    return reponse