import os
import sys
from pathlib import Path
import grpc
from concurrent import futures
import sqlite3
from dotenv import load_dotenv
import identity_pb2
import identity_pb2_grpc
import signal 

# Add dist/ to Python path for stub imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dist"))

# Load environment variables
load_dotenv()

# Database file path and encryption key
DB_PATH = Path(os.path.abspath("../waw-identity/identity.db"))
MASTER_KEY = os.getenv("waw_MASTER_KEY", "dummy_key")
print(f"📌 Identity DB path: {DB_PATH.resolve()}")

class DatabaseManager:
    """Handles all database operations including initialization and CRUD operations."""

    def __init__(self, db_path: Path, master_key: str):
        self.db_path = db_path
        self.master_key = master_key
        self.conn = self.init_db()

    def init_db(self):
        """Initializes the database with SQLCipher encryption."""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute(f"PRAGMA key = '{self.master_key}';")

        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS profile (
                id TEXT PRIMARY KEY,
                name TEXT,
                email TEXT,
                phone TEXT,
                created_at TEXT,
                updated_at TEXT
            );
        """
        )
        conn.commit()
        return conn

    def execute_query(self, query: str, params: tuple = ()):
        """Executes a query and returns the results."""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def commit(self):
        """Commits the transaction."""
        self.conn.commit()

    def close(self):
        """Closes the database connection."""
        self.conn.close()

class IdentityService(identity_pb2_grpc.IdentityServiceServicer):
    """Handles the profile CRUD operations via gRPC."""

    def __init__(self):
        self.db_manager = DatabaseManager(DB_PATH, MASTER_KEY)

    def GetProfile(self, request, context):
        try:
            row = self.db_manager.execute_query(
                "SELECT id, name, email, phone, created_at, updated_at FROM profile LIMIT 1;"
            )
            if not row:
                return identity_pb2.UserProfile()
            return identity_pb2.UserProfile(
                id=row[0][0],
                name=row[0][1],
                email=row[0][2],
                phone=row[0][3],
                created_at=row[0][4],
                updated_at=row[0][5],
            )
        except sqlite3.DatabaseError as e:
            context.set_details(f"Database error: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return identity_pb2.UserProfile()  # Or appropriate error response

    def UpdateProfile(self, request, context):
        try:
            profile = request.profile
            query = """
                INSERT OR REPLACE INTO profile (id, name, email, phone, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            self.db_manager.execute_query(
                query,
                (
                    profile.id,
                    profile.name,
                    profile.email,
                    profile.phone,
                    profile.created_at,
                    profile.updated_at,
                ),
            )
            self.db_manager.commit()
            return profile
        except sqlite3.DatabaseError as e:
            context.set_details(f"Database error: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return identity_pb2.UserProfile()  # Or appropriate error response

    def DeleteProfile(self, request, context):
        try:
            self.db_manager.execute_query(
                "DELETE FROM profile WHERE id = ?", (request.id,)
            )
            self.db_manager.commit()
            return identity_pb2.Empty()
        except sqlite3.DatabaseError as e:
            context.set_details(f"Database error: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return identity_pb2.Empty()

def handle_exit_signal(signal, frame):
    print("\nShutting down server...")
    server.stop(0)
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit_signal)

def serve():
    """Sets up and runs the gRPC server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
    identity_pb2_grpc.add_IdentityServiceServicer_to_server(
        IdentityService(), server)
    server.add_insecure_port("[::]:50051")
    print("🚀 IdentityService running on port 50051")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
