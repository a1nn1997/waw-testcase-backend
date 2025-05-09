"""
FastAPI service for managing user profiles in-memory and serving the
latest model file.
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

app = FastAPI()

# ─── CORS Middleware ────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProfileManager:
    """In-memory store for CRUD operations on profiles."""

    def __init__(self):
        self.store: Dict[str, dict] = {}

    def upsert(self, profile: dict) -> dict:
        """Insert or update a profile."""
        self.store[profile["id"]] = profile
        return self.store[profile["id"]]

    def delete(self, profile_id: str) -> bool:
        """Delete a profile by ID."""
        return self.store.pop(profile_id, None) is not None

    def get(self, profile_id: str) -> Optional[dict]:
        """Retrieve a profile by ID."""
        return self.store.get(profile_id)

    def all_profiles(self) -> Dict[str, dict]:
        """Return all stored profiles."""
        return self.store


class Profile(BaseModel):
    """Schema for profile data."""
    id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    updated_at: int

    @field_validator("updated_at", mode="before")
    @classmethod
    def _parse_updated_at(cls, v):
        # if client passed an ISO string, parse it
        if isinstance(v, str):
            # datetime.fromisoformat accepts "2025-05-09T07:09:13.358045+00:00"
            dt = datetime.fromisoformat(v)
            return int(dt.timestamp())
        return v

class UpsertResponse(BaseModel):
    """Response schema for profile upsert."""
    status: str
    count: int
    stored: dict


profile_manager = ProfileManager()


@app.post("/profile", response_model=UpsertResponse)
def upsert_profile(profile: Profile = Body(...)):
    """Create or update a profile and return status."""
    data = profile.model_dump()
    stored = profile_manager.upsert(data)
    stored["updated_at"] = (
        datetime.utcfromtimestamp(data["updated_at"]).isoformat() + "Z"
    )
    return {
        "status": "ok",
        "count": len(profile_manager.all_profiles()),
        "stored": stored,
    }


@app.get("/model/latest")
def get_latest_model():
    """Serve the latest model file along with its SHA256 checksum header."""
    model_path = Path(__file__).parent / "model.bin"
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="Model not found")

    checksum = hashlib.sha256(model_path.read_bytes()).hexdigest()
    return FileResponse(
        path=model_path,
        filename="model.bin",
        media_type="application/octet-stream",
        headers={"X-Model-SHA256": checksum},
    )


@app.delete("/profile/{profile_id}")
def delete_profile(profile_id: str):
    """Delete a profile by ID or return 404 if not found."""
    if profile_manager.delete(profile_id):
        return {"status": "deleted", "id": profile_id}
    raise HTTPException(status_code=404, detail="Profile not found")
