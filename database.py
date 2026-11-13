import sqlite3
import hashlib
import hmac
import secrets
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "fintrack.db"

PBKDF2_ITERATIONS = 600_000


def get_connection():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(password):
    salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS
    )

    return (
        f"pbkdf2_sha256${PBKDF2_ITERATIONS}$"
        f"{salt.hex()}${password_hash.hex()}"
    )


def verify_password(password, stored_hash):
    try:
        algorithm, iterations, salt_hex, hash_hex = (
            stored_hash.split("$")
        )

        if algorithm != "pbkdf2_sha256":
            return False

        calculated_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations)
        )

        return hmac.compare_digest(
            calculated_hash.hex(),
            hash_hex
        )

    except (ValueError, TypeError, AttributeError):
        return False


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create the expenses table only if it does not exist.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                category TEXT NOT NULL,
                date TEXT NOT NULL
            )
        """)

        # Migrate the existing table without deleting its rows.
        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(expenses)"
            ).fetchall()
        }

        if "user_id" not in columns:
            conn.execute("""
                ALTER TABLE expenses
                ADD COLUMN user_id INTEGER REFERENCES users(id)
            """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_expenses_user_date
            ON expenses(user_id, date)
        """)


def register_user(username, password):
    username = username.strip()

    if not 3 <= len(username) <= 30:
        return False, "Username must be 3–30 characters."

    if not all(
        ch.isalnum() or ch in "_-"
        for ch in username
    ):
        return False, (
            "Username can contain letters, numbers, _ and - only."
        )

    if len(password) < 8:
        return False, "Password must contain at least 8 characters."

    with get_connection() as conn:
        existing_user = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if existing_user:
            return False, "Username already exists."

        # Only the first account claims legacy, unassigned expenses.
        user_count = conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        password_hash = hash_password(password)

        cursor = conn.execute("""
            INSERT INTO users (username, password_hash)
            VALUES (?, ?)
        """, (username, password_hash))

        new_user_id = cursor.lastrowid

        if user_count == 0:
            conn.execute("""
                UPDATE expenses
                SET user_id = ?
                WHERE user_id IS NULL
            """, (new_user_id,))

    return True, "Registration successful. Please log in."


def authenticate_user(username, password):
    with get_connection() as conn:
        user = conn.execute("""
            SELECT id, username, password_hash
            FROM users
            WHERE username = ?
        """, (username.strip(),)).fetchone()

    if user and verify_password(password, user["password_hash"]):
        return {
            "id": user["id"],
            "username": user["username"]
        }

    return None


def add_expense(user_id, description, amount, category, expense_date):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO expenses
                (user_id, description, amount, category, date)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            description.strip(),
            float(amount),
            category,
            expense_date
        ))


def get_expenses(user_id):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, description, amount, category, date
            FROM expenses
            WHERE user_id = ?
            ORDER BY date DESC, id DESC
        """, (user_id,)).fetchall()

    return [dict(row) for row in rows]


def get_total_expenses(user_id):
    with get_connection() as conn:
        result = conn.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM expenses
            WHERE user_id = ?
        """, (user_id,)).fetchone()

    return float(result[0])


def get_monthly_expenses(user_id, month_key):
    with get_connection() as conn:
        result = conn.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM expenses
            WHERE user_id = ?
              AND substr(date, 1, 7) = ?
        """, (user_id, month_key)).fetchone()

    return float(result[0])


def delete_expense(user_id, expense_id):
    with get_connection() as conn:
        cursor = conn.execute("""
            DELETE FROM expenses
            WHERE id = ? AND user_id = ?
        """, (expense_id, user_id))

    return cursor.rowcount > 0


# Automatically create/migrate tables when this module is imported.
init_db()