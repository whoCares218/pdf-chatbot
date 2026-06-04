from google import genai
from dotenv import load_dotenv
import os
import chromadb
import time
import uuid

load_dotenv()

client_google = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

client_chroma = chromadb.PersistentClient(path="chroma_database")

collection = client_chroma.get_or_create_collection(
    name="pdf_text_chunks"
)

def store_pdf_in_chroma(chunks_metadata, session_id):

    embeddings = []
    documents = []
    metadatas = []
    ids = []

    for index, chunk_metadata in enumerate(chunks_metadata):

        chunk = chunk_metadata["chunk"]

        try:
            response = client_google.models.embed_content(
                model="gemini-embedding-2",
                contents=chunk
            )

        except Exception:

            print("Rate limit hit... waiting 20 seconds")

            time.sleep(20)

            response = client_google.models.embed_content(
                model="gemini-embedding-2",
                contents=chunk
            )

        embeddings.append(
            response.embeddings[0].values
        )

        documents.append(chunk)

        metadatas.append({
            "session_id": str(session_id),
            "source": chunk_metadata["source"],
            "page": chunk_metadata["page_number"]
        })

        ids.append(str(uuid.uuid4()))

    collection.add(
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids
    )

    print("Stored:", len(documents))