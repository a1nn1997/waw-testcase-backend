"""
Script to delete all profiles from the local encrypted SQLite database
via SQLCipher.
"""

import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv


# Load environment variables
load_dotenv()

# Constants
DB_PATH = Path(__file__).resolve().parents[1] / "waw-identity" / "identity.db"
MASTER_KEY = os.getenv("waw_MASTER_KEY", "dummy_key")


class DatabaseManager:
    """Handles database connections and operations."""

    def __init__(self, db_path: Path, master_key: str):
        self.db_path = db_path
        self.master_key = master_key
        self.conn = None

    def connect(self):
        """Establish an encrypted connection to the SQLite database."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"No profile DB found at {self.db_path}")

        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute(f"PRAGMA key = '{self.master_key}';")

    def execute_query(self, query: str, params: tuple = ()):
        """Execute a parameterized SQL query and commit."""
        if self.conn is None:
            raise ConnectionError("Database connection is not established.")

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()

    def close(self):
        """Close the database connection if open."""
        if self.conn:
            self.conn.close()


def delete_local_profile():
    """Delete all entries from the profile table."""
    db = DatabaseManager(DB_PATH, MASTER_KEY)
    try:
        db.connect()
        db.execute_query("DELETE FROM profile;")
        print("🗑️  Local profiles deleted successfully.")
    except Exception as error:
        print(f"❌ Error deleting profiles: {error}")
    finally:
        db.close()


if __name__ == "__main__":
    delete_local_profile()
