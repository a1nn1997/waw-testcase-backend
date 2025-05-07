import hashlib
import sqlite3
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Ensure sync_loop module is importable
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "src")
)

import sync_loop  # noqa: E402
from sync_loop import FileManager, ProfileDB, ProfileSync  # noqa: E402
from sync_loop import ModelSync, CLOUD_URL  # noqa: E402

load_dotenv()

TEST_DB = Path("/tmp/test_identity.db")
if TEST_DB.exists():
    TEST_DB.unlink()

# Initialize a fresh SQLite schema
conn = sqlite3.connect(TEST_DB)
conn.execute(
    "CREATE TABLE profile ("
    "id TEXT PRIMARY KEY, name TEXT, email TEXT, phone TEXT, "
    "created_at TEXT, updated_at TEXT"
    ");"
)
conn.commit()
conn.close()


@pytest.fixture(autouse=True)
def env_vars(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILE_DB_PATH", str(TEST_DB))
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(sync_loop, "STATE_PATH", state_file)
    monkeypatch.setenv("CLOUD_SYNC_URL", "http://example.com/profile")
    yield


def test_filemanager_state(tmp_path):
    assert FileManager.get_last_synced_at() is None
    FileManager.set_last_synced_at(123)
    assert FileManager.get_last_synced_at() == 123


def test_profiledb_get_and_delete():
    db = ProfileDB(TEST_DB, "dummy_key")
    conn = db._connect()
    conn.execute(
        "INSERT INTO profile VALUES "
        "('1','A','a@b.com','123','t','t');"
    )
    conn.commit()
    conn.close()

    prof = db.get_profile()
    assert prof["id"] == "1"

    db.delete_profile("1")
    assert db.get_profile() is None


def test_profilesync_no_profile():
    db = ProfileDB(TEST_DB, "dummy_key")
    sync = ProfileSync(db, CLOUD_URL)
    db.delete_profile("1")
    sync.sync_profile()


def test_modelsync(tmp_path, monkeypatch):
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    model_file = model_dir / "model.bin"
    model_file.write_bytes(b"abc")

    server_sha = hashlib.sha256(b"abc").hexdigest()

    class DummyResponse:
        status_code = 200
        headers = {"X-Model-SHA256": server_sha}

        def iter_content(self, chunk_size):
            yield b"abc"

    monkeypatch.setenv("CLOUD_SYNC_URL", "http://example.com/profile")
    monkeypatch.setattr(
        sync_loop.requests,
        "get",
        lambda *args, **kwargs: DummyResponse(),
    )

    sync = ModelSync("http://example.com/profile")
    sync.sync_model()
