from flask import Flask, render_template, request
from dotenv import load_dotenv
import os
import psycopg2

from retriever import search
from generator import generate_answer
from google import genai

from werkzeug.utils import secure_filename
from loader import load_pdf
from vectorstore import store_pdf_in_chroma

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

connection = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)

cursor = connection.cursor()

print("PostgreSQL connected successfully")

app = Flask(__name__)

def create_session(session_title="New Chat"):

    cursor.execute(
        """
        INSERT INTO sessions (title)
        VALUES (%s)
        RETURNING id
        """,
        (session_title,)
    )

    session_id = cursor.fetchone()[0]

    connection.commit()

    return session_id

def save_message(session_id, role, content):

    cursor.execute(
        """
        INSERT INTO messages (session_id, role, content)
        VALUES (%s, %s, %s)
        """,
        (session_id, role, content)
    )

    connection.commit()

def get_history(session_id):

    cursor.execute(
        """
        SELECT role, content
        FROM messages
        WHERE session_id = %s
        ORDER BY created_at
        """,
        (session_id,)
    )

    messages = cursor.fetchall()

    history = []

    for role, content in messages:

        history.append({
            "role": role,
            "content": content
        })

    return history

def get_all_sessions():

    cursor.execute(
        """
        SELECT id, title
        FROM sessions
        ORDER BY created_at DESC
        """
    )

    sessions = cursor.fetchall()

    all_sessions = []

    for session_id, title in sessions:

        all_sessions.append({
            "id": session_id,
            "title": title
        })

    return all_sessions

def update_session_title(session_id, title):

    cursor.execute(
        """
        UPDATE sessions
        SET title = %s
        WHERE id = %s
        """,
        (title, session_id)
    )

    connection.commit()

def generate_chat_title(history):

    prompt = f"""
    Generate a short professional chat title in 3-6 words maximum.

    Conversation:
    {history}

    Return only title.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text.strip()

@app.route("/", methods=["GET", "POST"])
def home():

    history = []

    if request.method == "POST":

        session_id = int(request.form["session_id"])

        query = request.form["query"]

        history = get_history(session_id)

        save_message(session_id, "user", query)

        result = search(query, session_id)

        answer = generate_answer(
            query,
            result,
            history
        )

        save_message(session_id, "model", answer)

        history = get_history(session_id)

        if len(history) == 2:

            title = generate_chat_title(history)

            update_session_title(
                session_id,
                title
            )

    sessions = get_all_sessions()

    session_pdfs = []

    if request.method == "POST":
        session_pdfs = get_session_pdfs(session_id)

    return render_template(
        "index.html",
        history=history,
        sessions=sessions,
        session_pdfs=session_pdfs
    )

@app.route("/create_new_session")
def create_new_session():

    session_id = create_session()

    return {
        "session_id": session_id
    }

@app.route("/load_session/<int:session_id>")
def load_session(session_id):

    history = get_history(session_id)

    pdfs = get_session_pdfs(session_id)

    return {
        "history": history,
        "pdfs": pdfs
    }

@app.route("/rename_session", methods=["POST"])
def rename_session():

    session_id = request.form["session_id"]
    title = request.form["title"]

    update_session_title(session_id, title)

    return {
        "message": "Session title updated"
    }
def save_pdf(session_id, file_name, file_path):

    cursor.execute(
        """
        INSERT INTO pdfs (session_id, file_name, file_path)
        VALUES (%s, %s, %s)
        """,
        (session_id, file_name, file_path)
    )

    connection.commit()

def get_session_pdfs(session_id):

    cursor.execute(
        """
        SELECT file_name
        FROM pdfs
        WHERE session_id = %s
        ORDER BY uploaded_at DESC
        """,
        (session_id,)
    )

    return [row[0] for row in cursor.fetchall()]

@app.route("/upload_pdf", methods=["POST"])
def upload_pdf():

    session_id = request.form["session_id"]

    pdfs = request.files.getlist("pdfs")

    upload_folder = f"uploads/{session_id}"

    os.makedirs(upload_folder, exist_ok=True)

    for pdf in pdfs:

        filename = secure_filename(pdf.filename)

        file_path = os.path.join(upload_folder, filename)

        pdf.save(file_path)

        save_pdf(session_id, filename, file_path)

        chunks_metadata = load_pdf(file_path)

        store_pdf_in_chroma(
            chunks_metadata,
            session_id
        )

    return {
        "message": "PDFs uploaded successfully"
    }
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)