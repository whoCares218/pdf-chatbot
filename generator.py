from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def generate_answer(query, results, history):
    if not results["documents"]:
        return "No relevant information found in the PDFs."
    chunks = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    context = ""

    filtered_chunks = []
    filtered_metadatas = []
    filtered_distances = []


    for chunk, metadata, distance in zip(chunks, metadatas, distances):
        if distance > 1 :
            continue

        filtered_chunks.append(chunk)
        filtered_metadatas.append(metadata)
        filtered_distances.append(distance)

        context += f"""
        Source: {metadata["source"]}
        Page: {metadata["page"]}
        Similarity Score: {distance}

        {chunk}

        -------------------
        """
    if not filtered_chunks:
        return "No relevant information found in the PDFs."
    
    sources=set()

    for metadata in filtered_metadatas:
        sources.add(f'{metadata["source"]} | Page {metadata["page"]}')

    conversation = ""

    for message in history:

        role = message["role"]
        content = message["content"]

        conversation += f"{role}: {content}\n"

    prompt = f"""
You are a helpful assistant.

Use ONLY the provided context to answer.

Conversation History:
{conversation}

Context:
{context}

Question:
{query}

Answer:
"""

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt
    )

    final_answer = response.text + "\n\nSources:\n"
    for source in sources:
        final_answer+=source
        final_answer+="\n"
    # final_answer += "\n\nChunks:\n"
    # for chunk in filtered_chunks:
    #     final_answer+=chunk
    #     final_answer += "\n\n--------------------------------------------\n"    
    
    return final_answer