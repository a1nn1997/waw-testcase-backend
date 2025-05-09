"""
Sync loop: periodically sync the local profile and model with the
cloud service.
"""

import json
import os
import sqlite3
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

# ─── Configuration ─────────────────────────────────────────────────────────

load_dotenv()

MASTER_KEY = os.getenv("waw_MASTER_KEY", "dummy_key")
DB_PATH = Path(os.getenv("PROFILE_DB_PATH", "identity.db"))
STATE_PATH = Path(
    os.path.expanduser(
        os.getenv("STATE_FILE", "~/.waw/state.json")
    )
)
CLOUD_URL = os.getenv("CLOUD_SYNC_URL", "")


# ─── FileManager ───────────────────────────────────────────────────────────

class FileManager:
    """Handles local state and file operations."""

    @staticmethod
    def get_last_synced_at() -> Optional[int]:
        """Retrieve the last sync timestamp from state file."""
        if STATE_PATH.exists():
            with STATE_PATH.open() as f:
                data = json.load(f)
            return data.get("last_synced_at")
        return None

    @staticmethod
    def set_last_synced_at(ts: int) -> None:
        """Write the last sync timestamp to state file."""
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with STATE_PATH.open("w") as f:
            json.dump({"last_synced_at": ts}, f)

    @staticmethod
    def get_local_model_sha(model_path: Path) -> Optional[str]:
        """Compute SHA256 of the local model file."""
        if model_path.exists():
            return hashlib.sha256(model_path.read_bytes()).hexdigest()
        return None

    @staticmethod
    def save_file(model_path: Path, response: requests.Response) -> None:
        """Save streamed response content to disk."""
        model_path.parent.mkdir(parents=True, exist_ok=True)
        with model_path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)


# ─── ProfileDB ─────────────────────────────────────────────────────────────

class ProfileDB:
    """Encrypted SQLite database access for UserProfile."""

    def __init__(self, db_path: Path, master_key: str):
        self.db_path = db_path
        self.master_key = master_key

    def _connect(self) -> sqlite3.Connection:
        """Open encrypted SQLite connection."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(f"PRAGMA key = '{self.master_key}';")
        return conn

    def get_profile(self) -> Optional[dict]:
        """Fetch the first profile row as a dict, or None if missing."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, email, phone, created_at, updated_at "
            "FROM profile LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        keys = ["id", "name", "email", "phone", "created_at", "updated_at"]
        return dict(zip(keys, row))

    def delete_profile(self, profile_id: str) -> None:
        """Delete a profile by ID."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM profile WHERE id = ?", (profile_id,))
        conn.commit()
        conn.close()


# ─── ProfileSync ───────────────────────────────────────────────────────────

class ProfileSync:
    """Syncs the local profile to the cloud service."""

    def __init__(self, profile_db: ProfileDB, cloud_url: str):
        self.profile_db = profile_db
        self.cloud_url = cloud_url

    def sync_profile(self) -> None:
        """POST profile if it has changed since last sync."""
        profile = self.profile_db.get_profile()
        if not profile:
            print("⚠️  No profile found in DB.")
            return

        try:
            updated_ts = int(datetime.fromisoformat(
                profile["updated_at"]
            ).timestamp())
        except Exception as e:
            print(f"⚠️  Invalid timestamp: {e}")
            updated_ts = 0

        last_synced = FileManager.get_last_synced_at()
        if last_synced != updated_ts:
            print("📤 Detected change, syncing profile...")
            # overwrite the field with an integer
            profile["updated_at"] = updated_ts
            print(f"sync url: {self.cloud_url} with payload: {str(profile)} called")
            resp = requests.post(self.cloud_url, json=profile)
            if resp.status_code == 200:
                FileManager.set_last_synced_at(updated_ts)
                print("✅ Sync successful.")
            else:
                print(f"❌ Sync failed: {resp.status_code} {resp.text}")
        else:
            print("⏳ No profile changes detected.")


# ─── ModelSync ─────────────────────────────────────────────────────────────

class ModelSync:
    """Fetches and updates the model binary from the cloud."""

    def __init__(self, cloud_url: str):
        self.cloud_url = cloud_url.rstrip("/profile")

    def sync_model(self) -> None:
        """Download the latest model if checksum differs."""
        model_path = Path.home() / ".waw" / "models" / "model.bin"
        print("🔍 Checking for model update...")
        try:
            resp = requests.get(f"{self.cloud_url}/model/latest", stream=True)
        except Exception as e:
            print(f"🔥 Model fetch error: {e}")
            return

        if resp.status_code != 200:
            print(f"⚠️  Model fetch failed: {resp.status_code}")
            return

        server_sha = resp.headers.get("X-Model-SHA256")
        local_sha = FileManager.get_local_model_sha(model_path)

        if server_sha and server_sha == local_sha:
            print("🆗 Model is up to date.")
        else:
            FileManager.save_file(model_path, resp)
            new_sha = FileManager.get_local_model_sha(model_path)
            if new_sha == server_sha:
                print(f"✅ Model updated: {model_path}")
            else:
                print("❌ SHA mismatch, discarding model.")
                model_path.unlink(missing_ok=True)


# ─── Main Loop ─────────────────────────────────────────────────────────────

def main_loop() -> None:
    """Run continuous sync of profile and model."""
    print("🔁 Starting waw-sync loop (every 60s)...")
    db = ProfileDB(DB_PATH, MASTER_KEY)
    p_sync = ProfileSync(db, CLOUD_URL)
    m_sync = ModelSync(CLOUD_URL)

    while True:
        try:
            p_sync.sync_profile()
        except Exception as e:
            print(f"🔥 Profile sync error: {e}")

        time.sleep(1)

        try:
            m_sync.sync_model()
        except Exception as e:
            print(f"🔥 Model sync error: {e}")

        time.sleep(60)


if __name__ == "__main__":
    print(f"🔍 Testing DB at: {DB_PATH}")
    ProfileDB(DB_PATH, MASTER_KEY).get_profile()
    main_loop()
