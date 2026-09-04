import os
from flask import Flask, request, jsonify
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

# Simple connection pool (min 1, max 10 connections)
connection_pool = psycopg2.pool.SimpleConnectionPool(1, 10, **DB_CONFIG)


def get_conn():
    return connection_pool.getconn()


def put_conn(conn):
    connection_pool.putconn(conn)


def init_db():
    """Create the users table if it doesn't exist."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                );
                """
            )
        conn.commit()
    finally:
        put_conn(conn)


# ---------------- Routes ----------------

@app.route("/", methods=["GET"])
def index():
    """Root route — lists available endpoints so hitting / doesn't 404."""
    return jsonify({
        "service": "flask-postgres-users-api",
        "endpoints": {
            "GET /health": "health check",
            "GET /api/users": "list all users",
            "POST /api/users": "create a user (JSON body: name, email)",
            "GET /api/users/<id>": "get a single user by id",
        },
    }), 200


@app.route("/health", methods=["GET"])
def health():
    """Basic health check, also verifies DB connectivity."""
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        finally:
            put_conn(conn)
        return jsonify({"status": "ok", "db": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "error", "db": "unreachable", "detail": str(e)}), 500


@app.route("/api/users", methods=["GET"])
def get_users():
    """Return all users."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, name, email, created_at FROM users ORDER BY id;")
            rows = cur.fetchall()
        return jsonify([dict(r) for r in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        put_conn(conn)


@app.route("/api/users", methods=["POST"])
def create_user():
    """Create a new user from JSON body: {"name": "...", "email": "..."}"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    name = data.get("name")
    email = data.get("email")

    if not name or not email:
        return jsonify({"error": "'name' and 'email' are required"}), 400

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO users (name, email)
                VALUES (%s, %s)
                RETURNING id, name, email, created_at;
                """,
                (name, email),
            )
            new_user = cur.fetchone()
        conn.commit()
        return jsonify(dict(new_user)), 201
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({"error": f"User with email '{email}' already exists"}), 409
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        put_conn(conn)


@app.route("/api/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """Return a single user by id."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, email, created_at FROM users WHERE id = %s;",
                (user_id,),
            )
            user = cur.fetchone()
        if user is None:
            return jsonify({"error": f"User {user_id} not found"}), 404
        return jsonify(dict(user)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        put_conn(conn)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
