"""Firebase auth middleware and token verification."""

import logging
import os
import firebase_admin
from firebase_admin import credentials, auth
from fastapi import Request, HTTPException, status

# Initialize Firebase Admin (lazy init on first use)
_firebase_initialized = False


def _ensure_firebase_init():
    global _firebase_initialized
    if not _firebase_initialized:
        project_id = os.environ.get("FIREBASE_PROJECT_ID")
        if not project_id:
            raise RuntimeError("FIREBASE_PROJECT_ID environment variable is required")
        cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path and os.path.isfile(cred_path):
            cred = credentials.Certificate(cred_path)
        else:
            cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {"projectId": project_id})
        _firebase_initialized = True


async def get_current_uid(request: Request) -> str:
    """Extract and verify Firebase ID token, return uid. Raises 401 if invalid."""
    # Dev mode: bypass Firebase when DEV_MODE=1 and X-Dev-User-Id is set
    if os.environ.get("DEV_MODE") == "1":
        dev_uid = request.headers.get("X-Dev-User-Id")
        if dev_uid:
            return dev_uid.strip()

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "invalid_token", "message": "Missing or invalid Authorization header"}},
        )
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "invalid_token", "message": "Missing token"}},
        )

    try:
        _ensure_firebase_init()
        decoded = auth.verify_id_token(token)
        uid = decoded.get("uid")
        if not uid:
            raise ValueError("No uid in token")
        return uid
    except Exception as e:
        logging.warning("Firebase token verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "invalid_token", "message": str(e) or "Invalid or expired token"}},
        )
