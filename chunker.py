def chunk_text(text,chunk_size=500,chunk_overlap=100):
    chunks=[]

    start=0
    while start < len(text):
        end=start+chunk_size

        chunks.append(text[start:end])

        start=end-chunk_overlap
        
        if start < 0 :
            start = 0

    return chunks

# chunks=chunk_text(text)

# print("TOTAL CHUNKS : ",len(chunks))

