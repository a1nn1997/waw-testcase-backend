"""
Integration test for IdentityService: update then fetch a UserProfile.
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import grpc
from dotenv import load_dotenv

import identity_pb2
import identity_pb2_grpc


# Load environment variables
load_dotenv()


class ProfileDB:
    """Handles operations with the profile database."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.master_key = os.getenv("waw_MASTER_KEY", "dummy_key")

    def connect(self):
        """Connect to the database and apply the encryption key."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(f"PRAGMA key = '{self.master_key}';")
        return conn

    def clear_profiles(self):
        """Clear existing profiles from the database."""
        conn = self.connect()
        conn.execute("DELETE FROM profile;")
        conn.commit()
        print("⚠️ Cleared existing profiles in the database.")


class ProfileSync:
    """Handles profile synchronization via gRPC."""

    def __init__(self, channel: grpc.Channel):
        self.stub = identity_pb2_grpc.IdentityServiceStub(channel)

    def create_profile(self, profile: identity_pb2.UserProfile):
        """Create or update a profile using gRPC."""
        self.stub.UpdateProfile(identity_pb2.ProfileDelta(profile=profile))

    def get_profile(self) -> identity_pb2.UserProfile:
        """Fetch a profile from the gRPC server."""
        return self.stub.GetProfile(identity_pb2.Empty())


def test_update_and_get_profile():
    """Test case to update and fetch a profile."""
    db_path = (
        Path(__file__).resolve()
        .parents[2]
        / "waw-identity"
        / "identity.db"
    )
    profile_db = ProfileDB(db_path)
    profile_sync = ProfileSync(grpc.insecure_channel("localhost:50051"))

    # Clear any existing profile
    profile_db.clear_profiles()

    # Create a new test profile
    now = datetime.now().isoformat()
    profile = identity_pb2.UserProfile(
        id=str(uuid4()),
        name="Test User",
        email="test@user.com",
        phone="9999999999",
        created_at=now,
        updated_at=now,
    )

    # Push it via gRPC
    profile_sync.create_profile(profile)

    # Fetch it back and assert
    fetched = profile_sync.get_profile()
    assert (
        fetched.name == "Test User"
    ), f"Expected 'Test User', but got '{fetched.name}'"

    print("✅ test_update_and_get_profile passed.")


if __name__ == "__main__":
    test_update_and_get_profile()
