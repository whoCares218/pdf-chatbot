from flask import (
    Flask,
    render_template,
    request,
    session,
    redirect,
    jsonify
)
from auth import (
    create_user,
    get_user_by_email,
    save_otp,
    verify_otp,
    send_otp_email,
    login_user
)
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
import os

os.makedirs("uploads", exist_ok=True)
os.makedirs("chroma_database", exist_ok=True)
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
app.secret_key = os.getenv("SECRET_KEY")

@app.route("/signup", methods=["POST"])
def signup():

    email = request.form["email"]
    password = request.form["password"]

    existing_user = get_user_by_email(
        cursor,
        email
    )

    if existing_user:
        return {"message": "User already exists"}

    user_id = create_user(
        cursor,
        connection,
        email,
        password
    )

    otp = save_otp(
        cursor,
        connection,
        user_id
    )

    send_otp_email(
        email,
        otp
    )

    return {
        "message": "OTP sent",
        "user_id": user_id
    }

@app.route("/verify_otp", methods=["POST"])
def verify_user_otp():

    user_id = request.form["user_id"]
    otp = request.form["otp"]

    success = verify_otp(
    cursor,
    connection,
    int(user_id),
    otp
    )

    if not success:
        return {
            "message": "Invalid OTP"
        }

    create_session(
    int(user_id),
    "New Chat"
    )

    session["user_id"] = int(user_id)

    create_session(
        int(user_id),
        "New Chat"
    )

    return {
        "message": "Account verified"
    }

@app.route("/login", methods=["POST", "GET"])
def login():

    if request.method == "GET":
        if "user_id" in session:
            return redirect("/")
        
        return render_template("index.html")

    email = request.form["email"]
    password = request.form["password"]

    user_id = login_user(
        cursor,
        email,
        password
    )

    if not user_id:
        return {
            "message": "Invalid credentials"
        }

    session["user_id"] = user_id

    sessions = get_all_sessions(user_id)

    if len(sessions) == 0:
        create_session(user_id)

    return {
        "message": "Login successful"
    }

@app.route("/logout")
def logout():

    session.clear()

    return {
        "message": "Logged out"
    }

def create_session(user_id, session_title="New Chat"):

    cursor.execute(
        """
        INSERT INTO sessions (user_id, title)
        VALUES (%s, %s)
        RETURNING id
        """,
        (user_id, session_title)
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

def get_all_sessions(user_id):

    cursor.execute(
        """
        SELECT id, title
        FROM sessions
        WHERE user_id = %s
        ORDER BY created_at DESC
        """,
        (user_id,)
    )

    sessions = cursor.fetchall()

    all_sessions = []

    for session_id, title in sessions:

        all_sessions.append(
            {
                "id": session_id,
                "title": title
            }
        )

    return all_sessions

def session_belongs_to_user(session_id, user_id):

    cursor.execute(
        """
        SELECT id
        FROM sessions
        WHERE id = %s
        AND user_id = %s
        """,
        (session_id, user_id)
    )

    return cursor.fetchone() is not None

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

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    history = []
    session_pdfs = []

    if request.method == "POST":

        session_id = int(request.form["session_id"])

        if not session_belongs_to_user(
            session_id,
            user_id
        ):
            return {
                "message": "Access denied"
            }

        query = request.form["query"]

        history = get_history(session_id)

        save_message(
            session_id,
            "user",
            query
        )

        result = search(
            query,
            session_id
        )

        answer = generate_answer(
            query,
            result,
            history
        )

        save_message(
            session_id,
            "model",
            answer
        )

        history = get_history(session_id)

        session_pdfs = get_session_pdfs(
            session_id
        )

        if len(history) == 4:

            title = generate_chat_title(
                history
            )

            update_session_title(
                session_id,
                title
            )

    sessions = get_all_sessions(user_id)

    if request.method != "POST":

        if sessions:
            first_session_id = sessions[0]["id"]

            history = get_history(first_session_id)

            session_pdfs = get_session_pdfs(first_session_id)
        else:
            history = []
            session_pdfs = []

    return render_template(
        "index.html",
        history=history,
        sessions=sessions,
        session_pdfs=session_pdfs
    )

@app.route("/create_new_session")
def create_new_session():

    if "user_id" not in session:
        return {"message": "Login required"}

    user_id = session["user_id"]

    session_id = create_session(
        user_id
    )

    return {
        "session_id": session_id
    }

@app.route("/load_session/<int:session_id>")
def load_session(session_id):
    if "user_id" not in session:
        return {"message": "Login required"}

    user_id = session["user_id"]

    if not session_belongs_to_user(
        session_id,
        user_id
    ):
        return {
            "message": "Access denied"
        }
    
    history = get_history(session_id)

    pdfs = get_session_pdfs(session_id)

    return {
        "history": history,
        "pdfs": pdfs
    }

@app.route("/rename_session", methods=["POST"])
def rename_session():

    if "user_id" not in session:
        return {"message": "Login required"}

    session_id = int(
        request.form["session_id"]
    )

    title = request.form["title"]

    user_id = session["user_id"]

    if not session_belongs_to_user(
        session_id,
        user_id
    ):
        return {
            "message": "Access denied"
        }

    update_session_title(
        session_id,
        title
    )

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
    if "user_id" not in session:
        return {"message": "Login required"}
    
    session_id = int(
        request.form["session_id"]
    )

    user_id = session["user_id"]

    if not session_belongs_to_user(
        session_id,
        user_id
    ):
        return {
            "message": "Access denied"
        }

    pdfs = request.files.getlist(
        "pdfs"
    )

    upload_folder = f"uploads/{session_id}"

    os.makedirs(
        upload_folder,
        exist_ok=True
    )

    for pdf in pdfs:

        filename = secure_filename(
            pdf.filename
        )

        file_path = os.path.join(
            upload_folder,
            filename
        )

        pdf.save(file_path)

        save_pdf(
            session_id,
            filename,
            file_path
        )

        chunks_metadata = load_pdf(
            file_path
        )

        store_pdf_in_chroma(
            chunks_metadata,
            session_id
        )

    return {
        "message": "PDFs uploaded successfully"
    }

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)