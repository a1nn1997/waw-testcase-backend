import time
import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Add backend_mock directory to path so we can import app module
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "backend_mock"),
)

from app import app, profile_manager  # noqa: E402

client = TestClient(app)


def test_upsert_profile_only():
    """Test creating/updating a profile via POST /profile."""
    profile_manager.store.clear()
    payload = {
        "id": "1",
        "name": "Alice",
        "email": "alice@example.com",
        "phone": "1234567890",
        "updated_at": int(time.time()),
    }
    response = client.post("/profile", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["count"] == 1
    assert data["stored"]["id"] == "1"


def test_delete_profile_not_found():
    """Deleting a non-existent profile returns 404."""
    profile_manager.store.clear()
    response = client.delete("/profile/nonexistent")
    assert response.status_code == 404
