from google import genai
import chromadb
import os
from dotenv import load_dotenv

load_dotenv()

# Gemini client
client_google = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

# ChromaDB persistent storage
client_chroma = chromadb.PersistentClient(
    path="chroma_database"
)

# -------------------------
# SAFE COLLECTION HANDLING
# -------------------------
def get_collection():
    try:
        return client_chroma.get_collection("pdf_text_chunks")
    except Exception:
        return client_chroma.create_collection("pdf_text_chunks")


# -------------------------
# MAIN SEARCH FUNCTION
# -------------------------
def search(query, session_id, k=3):

    collection = get_collection()

    # 1. Create embedding using Gemini
    response = client_google.models.embed_content(
        model="gemini-embedding-2.0",
        contents=query
    )

    query_embedding = response.embeddings[0].values

    # 2. Query ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        where={
            "session_id": str(session_id)
        }
    )

    return results