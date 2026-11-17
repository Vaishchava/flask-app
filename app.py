import os
from flask import Flask, request, redirect, url_for, render_template_string
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# --- Database config (from environment variables) ---
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "flaskdb"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}

connection_pool = psycopg2.pool.SimpleConnectionPool(1, 10, **DB_CONFIG)


def get_conn():
    return connection_pool.getconn()


def put_conn(conn):
    connection_pool.putconn(conn)


def init_db():
    """Create the notes table if it doesn't exist."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                );
                """
            )
        conn.commit()
    finally:
        put_conn(conn)


# ---------------- HTML template (inline, no separate templates folder needed) ----------------

PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>My Notes</title>
  <style>
    body {
      font-family: -apple-system, Segoe UI, Roboto, sans-serif;
      background: #f4f4f6;
      margin: 0;
      padding: 40px 20px;
      color: #222;
    }
    .container {
      max-width: 600px;
      margin: 0 auto;
    }
    h1 {
      margin-bottom: 20px;
    }
    form {
      display: flex;
      gap: 8px;
      margin-bottom: 30px;
    }
    textarea {
      flex: 1;
      padding: 10px;
      border: 1px solid #ccc;
      border-radius: 6px;
      font-size: 15px;
      resize: vertical;
      min-height: 44px;
    }
    button {
      padding: 0 18px;
      border: none;
      background: #4f46e5;
      color: white;
      border-radius: 6px;
      font-size: 15px;
      cursor: pointer;
    }
    button:hover {
      background: #4338ca;
    }
    .note {
      background: white;
      border-radius: 8px;
      padding: 14px 16px;
      margin-bottom: 12px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.08);
      position: relative;
    }
    .note p {
      margin: 0 0 8px 0;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .note small {
      color: #888;
    }
    .note form {
      margin: 0;
      position: absolute;
      top: 10px;
      right: 10px;
    }
    .delete-btn {
      background: transparent;
      color: #999;
      padding: 0 6px;
      font-size: 13px;
    }
    .delete-btn:hover {
      color: #d33;
      background: transparent;
    }
    .empty {
      color: #888;
      text-align: center;
      margin-top: 40px;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>📝 My Notes</h1>

    <form method="POST" action="{{ url_for('add_note') }}">
      <textarea name="content" placeholder="Write a note..." required></textarea>
      <button type="submit">Add</button>
    </form>

    {% if notes %}
      {% for note in notes %}
        <div class="note">
          <p>{{ note.content }}</p>
          <small>{{ note.created_at.strftime('%b %d, %Y %I:%M %p') }}</small>
          <form method="POST" action="{{ url_for('delete_note', note_id=note.id) }}">
            <button type="submit" class="delete-btn">✕</button>
          </form>
        </div>
      {% endfor %}
    {% else %}
      <p class="empty">No notes yet. Add one above!</p>
    {% endif %}
  </div>
</body>
</html>
"""


# ---------------- Routes ----------------

@app.route("/", methods=["GET"])
def index():
    """Show the form and list of all notes, newest first."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, content, created_at FROM notes ORDER BY id DESC;")
            notes = cur.fetchall()
        return render_template_string(PAGE_TEMPLATE, notes=notes)
    finally:
        put_conn(conn)


@app.route("/add", methods=["POST"])
def add_note():
    """Take note text from the form and store it in the database."""
    content = request.form.get("content", "").strip()
    if content:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO notes (content) VALUES (%s);", (content,))
            conn.commit()
        finally:
            put_conn(conn)
    return redirect(url_for("index"))


@app.route("/delete/<int:note_id>", methods=["POST"])
def delete_note(note_id):
    """Delete a note by id."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM notes WHERE id = %s;", (note_id,))
        conn.commit()
    finally:
        put_conn(conn)
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
