import time
import os
import json
import hashlib
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import sqlite3
from uuid import uuid4
from typing import Optional


# Load config
load_dotenv()

MASTER_KEY = os.getenv("waw_MASTER_KEY", "dummy_key")
DB_PATH = Path(os.getenv("PROFILE_DB_PATH", "identity.db"))
STATE_PATH = Path(os.path.expanduser(os.getenv("STATE_FILE", "~/.waw/state.json")))
CLOUD_URL = os.getenv("CLOUD_SYNC_URL")


# ----------------------------- Helpers ----------------------------- #

class FileManager:
    @staticmethod
    def get_last_synced_at() -> Optional[str]:
        """Retrieve the last sync timestamp from state file."""
        if STATE_PATH.exists():
            with open(STATE_PATH) as f:
                return json.load(f).get("last_synced_at")
        return None

    @staticmethod
    def set_last_synced_at(ts: str):
        """Set the last sync timestamp in the state file."""
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_PATH, "w") as f:
            json.dump({"last_synced_at": ts}, f)

    @staticmethod
    def get_local_model_sha(model_path: Path) -> Optional[str]:
        """Retrieve SHA of the model."""
        if model_path.exists():
            return hashlib.sha256(model_path.read_bytes()).hexdigest()
        return None

    @staticmethod
    def save_file(model_path: Path, res: requests.Response):
        """Save the model file to the disk."""
        model_path.parent.mkdir(parents=True, exist_ok=True)
        with open(model_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)


class ProfileDB:
    def __init__(self, db_path: Path, master_key: str):
        self.db_path = db_path
        self.master_key = master_key

    def _connect(self):
        """Establish a connection with the encrypted SQLite database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(f"PRAGMA key = '{self.master_key}';")
        return conn

    def get_profile(self) -> Optional[dict]:
        """Get profile from the database."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, phone, created_at, updated_at FROM profile LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return None
        keys = ["id", "name", "email", "phone", "created_at", "updated_at"]
        return dict(zip(keys, row))

    def delete_profile(self, profile_id: str):
        """Delete profile from the database."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM profile WHERE id=?", (profile_id,))
        conn.commit()


# ----------------------------- Sync Logic ----------------------------- #

class ProfileSync:
    def __init__(self, profile_db: ProfileDB, cloud_url: str):
        self.profile_db = profile_db
        self.cloud_url = cloud_url

    def sync_profile(self):
        """Sync the profile to the cloud if there are changes."""
        profile = self.profile_db.get_profile()
        if profile:
            try:
                profile["updated_at"] = int(datetime.fromisoformat(profile["updated_at"]).timestamp())
            except Exception as e:
                print(f"⚠️ Failed to convert 'updated_at': {e}")
                profile["updated_at"] = 0

            updated_at = profile["updated_at"]
            last_synced_at = FileManager.get_last_synced_at()

            if last_synced_at != updated_at:
                print("📤 Detected profile change, syncing...")
                res = requests.post(self.cloud_url, json=profile)
                if res.status_code == 200:
                    FileManager.set_last_synced_at(updated_at)
                    print("✅ Sync successful.")
                else:
                    print(f"❌ Sync failed: {res.status_code} - {res.text}")
            else:
                print("⏳ No changes detected.")
        else:
            print("⚠️ No profile found in DB.")


class ModelSync:
    def __init__(self, cloud_url: str):
        self.cloud_url = cloud_url

    def sync_model(self):
        """Sync the model from cloud and save it locally."""
        model_dir = Path(os.path.expanduser("~/.waw/models"))
        model_path = model_dir / "model.bin"
        print("🔍 Checking for model update...")

        try:
            res = requests.get(f"{self.cloud_url.replace('/profile', '')}/model/latest", stream=True)

            if res.status_code == 200:
                server_sha = res.headers.get("X-Model-SHA256")
                local_sha = FileManager.get_local_model_sha(model_path)

                if server_sha and server_sha == local_sha:
                    print("🆗 Model is already up to date.")
                else:
                    FileManager.save_file(model_path, res)

                    new_sha = FileManager.get_local_model_sha(model_path)
                    if new_sha == server_sha:
                        print(f"✅ Model updated and verified: {model_path}")
                    else:
                        print("❌ SHA mismatch! Model discarded.")
                        model_path.unlink(missing_ok=True)

            else:
                print(f"⚠️ Model fetch failed: {res.status_code}")

        except Exception as e:
            print(f"🔥 Model fetch error: {e}")


# ----------------------------- Main Loop ----------------------------- #

def main_loop():
    print("🔁 Starting waw-sync loop (every 60s)...")
    profile_db = ProfileDB(DB_PATH, MASTER_KEY)
    profile_sync = ProfileSync(profile_db, CLOUD_URL)
    model_sync = ModelSync(CLOUD_URL)

    while True:
        try:
            profile_sync.sync_profile()
        except Exception as e:
            print(f"🔥 Error: {e}")

        time.sleep(1)
        model_sync.sync_model()
        time.sleep(60)


if __name__ == "__main__":
    print("🔍 Testing DB at:", DB_PATH)
    profile_db = ProfileDB(DB_PATH, MASTER_KEY)
    profile_db.get_profile()  # Test DB decryption
    main_loop()
