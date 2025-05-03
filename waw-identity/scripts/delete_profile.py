import grpc
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
import os

# Add gRPC stubs
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dist"))

# Constants
DB_PATH = Path("waw-identity/identity.db")
load_dotenv()
MASTER_KEY = os.getenv("waw_MASTER_KEY", "dummy_key")


class DatabaseManager:
    """Handles database connections and operations."""

    def __init__(self, db_path: Path, master_key: str):
        self.db_path = db_path
        self.master_key = master_key
        self.conn = None

    def connect(self):
        """Connect to the SQLite database with encryption."""
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"⚠️  No profile DB found at {self.db_path}.")

        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute(f"PRAGMA key = '{self.master_key}';")

    def execute_query(self, query: str, params: tuple = ()):
        """Execute a query with parameters."""
        if self.conn is None:
            raise ConnectionError("Database connection is not established.")

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()


def delete_local_profile():
    """Deletes the local profile from the database."""
    db_manager = DatabaseManager(DB_PATH, MASTER_KEY)
    try:
        db_manager.connect()
        db_manager.execute_query("DELETE FROM profile;")
        print("🗑️  Local profile deleted.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db_manager.close()


if __name__ == "__main__":
    delete_local_profile()
