from pypdf import PdfReader
from chunker import chunk_text

def load_pdf(file_path):

    chunks_metadatas = []

    reader = PdfReader(file_path)

    page_number = 1

    for page in reader.pages:

        page_text = page.extract_text()

        if not page_text:
            page_number += 1
            continue

        paras = page_text.split("\n\n")

        for para in paras:

            if not para.strip():
                continue

            para_chunks = chunk_text(para)

            for para_chunk in para_chunks:

                chunks_metadatas.append({
                    "chunk": para_chunk,
                    "source": file_path.split("/")[-1],
                    "page_number": page_number
                })

        page_number += 1

    return chunks_metadatas