"""
gRPC server for IdentityService with SQLCipher-encrypted SQLite database.
"""

import logging
import sys
import os
import signal
import sqlite3
from concurrent import futures
from pathlib import Path

import grpc
from dotenv import load_dotenv

import identity_pb2
import identity_pb2_grpc


# Load environment variables
load_dotenv()

# Database file path and encryption key
DB_PATH = Path("../waw-identity/identity.db").resolve()
MASTER_KEY = os.getenv("waw_MASTER_KEY", "dummy_key")

logging.basicConfig(level=logging.INFO)
logging.info(f"📌 Identity DB path: {DB_PATH}")


class DatabaseManager:
    """Handles database initialization and CRUD operations."""

    def __init__(self, db_path: Path, master_key: str):
        self.db_path = db_path
        self.master_key = master_key
        self.conn = self._init_db()

    def _init_db(self):
        """Initializes an encrypted SQLite database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute(f"PRAGMA key = '{self.master_key}';")

        conn.execute(
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
        """Execute a SQL query and return all rows."""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def commit(self):
        """Commit the current transaction."""
        self.conn.commit()

    def close(self):
        """Close the database connection."""
        self.conn.close()


class IdentityService(identity_pb2_grpc.IdentityServiceServicer):
    """gRPC servicer providing profile CRUD operations."""

    def __init__(self):
        self.db_manager = DatabaseManager(DB_PATH, MASTER_KEY)

    def GetProfile(self, request, context):
        try:
            rows = self.db_manager.execute_query(
                "SELECT id, name, email, phone, created_at, updated_at "
                "FROM profile LIMIT 1;"
            )
            if not rows:
                return identity_pb2.UserProfile()

            row = rows[0]
            return identity_pb2.UserProfile(
                id=row[0],
                name=row[1],
                email=row[2],
                phone=row[3],
                created_at=row[4],
                updated_at=row[5],
            )

        except sqlite3.DatabaseError as err:
            context.set_details(f"Database error: {err}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return identity_pb2.UserProfile()

    def UpdateProfile(self, request, context):
        try:
            p = request.profile
            self.db_manager.execute_query(
                """
                INSERT OR REPLACE INTO profile
                (id, name, email, phone, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    p.id,
                    p.name,
                    p.email,
                    p.phone,
                    p.created_at,
                    p.updated_at,
                ),
            )
            self.db_manager.commit()
            return p

        except sqlite3.DatabaseError as err:
            context.set_details(f"Database error: {err}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return identity_pb2.UserProfile()

    def DeleteProfile(self, request, context):
        try:
            self.db_manager.execute_query(
                "DELETE FROM profile WHERE id = ?;", (request.id,)
            )
            self.db_manager.commit()
            return identity_pb2.Empty()

        except sqlite3.DatabaseError as err:
            context.set_details(f"Database error: {err}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return identity_pb2.Empty()


def serve():
    """Start the gRPC server and register the IdentityService."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
    identity_pb2_grpc.add_IdentityServiceServicer_to_server(
        IdentityService(), server
    )
    server.add_insecure_port("[::]:50051")

    # Handle graceful shutdown on Ctrl+C
    signal.signal(signal.SIGINT, lambda sig, frame: shutdown(server))

    logging.info("🚀 IdentityService running on port 50051")
    server.start()
    server.wait_for_termination()


def shutdown(server_obj):
    """Gracefully stop the gRPC server."""
    logging.info("Shutting down server...")
    server_obj.stop(0)
    sys.exit(0)


if __name__ == "__main__":
    serve()
