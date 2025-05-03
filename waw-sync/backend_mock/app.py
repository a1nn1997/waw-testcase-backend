from typing import Dict, Optional
from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from pathlib import Path
import hashlib
from datetime import datetime

app = FastAPI()

# ─── CORS (attach *after* app creation) ───────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── ProfileManager Class ─────────────────────────────────────────────────


class ProfileManager:
    """Handles the CRUD operations for profiles."""

    def __init__(self):
        self.store: Dict[str, dict] = {}

    def upsert(self, profile: dict) -> dict:
        """Insert or update the profile in the store."""
        self.store[profile["id"]] = profile
        return self.store[profile["id"]]

    def delete(self, profile_id: str):
        """Delete the profile from the store."""
        if profile_id in self.store:
            del self.store[profile_id]
            return True
        return False

    def get(self, profile_id: str) -> Optional[dict]:
        """Get the profile by its ID."""
        return self.store.get(profile_id)

    def all_profiles(self) -> Dict[str, dict]:
        """Get all profiles."""
        return self.store


# ─── Profile Schema ────────────────────────────────────────────────────────


class Profile(BaseModel):
    id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    updated_at: int


class UpsertResponse(BaseModel):
    status: str
    count: int
    stored: dict


# ─── Instantiate ProfileManager ───────────────────────────────────────────
profile_manager = ProfileManager()

# ─── POST /profile ────────────────────────────────────────────────────────


@app.post("/profile", response_model=UpsertResponse)
def upsert_profile(profile: Profile = Body(...)):
    profile_dict = profile.dict()  # Convert Pydantic model to dict
    # Upsert the profile into the profile manager
    stored_profile = profile_manager.upsert(profile_dict)

    # Format updated_at as ISO 8601 for readability
    stored_profile["updated_at"] = (
        datetime.utcfromtimestamp(
            stored_profile["updated_at"]).isoformat() + "Z")

    return {
        "status": "ok",
        "count": len(profile_manager.all_profiles()),
        "stored": stored_profile,
    }


# ─── GET /model/latest ────────────────────────────────────────────────────


@app.get("/model/latest")
def get_latest_model():
    MODEL_PATH = Path(__file__).parent / "model.bin"

    if not MODEL_PATH.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    sha256 = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    headers = {"X-Model-SHA256": sha256}

    return FileResponse(
        path=MODEL_PATH,
        filename="model.bin",
        media_type="application/octet-stream",
        headers=headers,
    )


# ─── DELETE /profile/{profile_id} ───────────────────────────────────────────


@app.delete("/profile/{profile_id}")
def delete_profile(profile_id: str):
    if profile_manager.delete(profile_id):
        return {"status": "deleted", "id": profile_id}
    raise HTTPException(status_code=404, detail="Profile not found")
