from google import genai
import chromadb
import os
from dotenv import load_dotenv

load_dotenv()

client_google = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

client_chroma = chromadb.PersistentClient(
    path="chroma_database"
)

# ---------- FIX 1: safe collection ----------
def get_collection():
    try:
        return client_chroma.get_collection("pdf_text_chunks")
    except Exception:
        return client_chroma.create_collection("pdf_text_chunks")


# ---------- FIX 2: correct function ----------
def search(query, session_id, k=3):

    collection = get_collection()   # IMPORTANT FIX

    response = client_google.models.embed_content(
        model="gemini-embedding-2",
        contents=query
    )

    query_embedding = response.embeddings[0].values

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        where={
            "session_id": str(session_id)
        }
    )

    return results