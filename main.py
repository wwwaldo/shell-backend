"""Navigator Chat Backend API."""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import os
import re
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from nanoid import generate

from database import init_db, get_db, User, Conversation, Message
from auth import get_current_uid
from inference import chat_completion, get_base_model

# --- Pydantic schemas ---


class ChatRequest(BaseModel):
    message: str


class AnthropicKeyRequest(BaseModel):
    api_key: str


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime


class ConversationSummary(BaseModel):
    id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int


class ConversationDetail(BaseModel):
    id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int


class ModelStatusResponse(BaseModel):
    has_adapter: bool
    adapter_version: int
    base_model: str


def error_response(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


# --- App setup ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Navigator Chat API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "https://shell-chat-3b8d2.web.app",
        "https://shell-chat-3b8d2.firebaseapp.com",
    ],
    allow_origin_regex=r"^https://[a-z0-9-]+\.(web\.app|firebaseapp\.com)$",
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)


# --- Exception handler for consistent error format ---


from fastapi.responses import JSONResponse


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # If detail is already in error format, use it
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    # Otherwise wrap it
    code = "internal_error"
    if exc.status_code == 401:
        code = "invalid_token"
    elif exc.status_code == 403:
        code = "forbidden"
    elif exc.status_code == 404:
        code = "not_found"
    elif exc.status_code == 429:
        code = "rate_limited"
    elif exc.status_code == 502:
        code = "inference_error"
    msg = str(exc.detail) if exc.detail else "An error occurred"
    return JSONResponse(status_code=exc.status_code, content=error_response(code, msg))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response("internal_error", "An unexpected error occurred"),
    )


# --- Helpers ---


def _get_or_create_user(db, uid: str) -> User:
    user = db.query(User).filter(User.uid == uid).first()
    if not user:
        user = User(uid=uid)
        db.add(user)
        db.flush()
    return user


def _ensure_conversation_owner(db, conv_id: str, uid: str) -> Conversation:
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response("not_found", "Conversation not found"),
        )
    if conv.user_id != uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_response("forbidden", "User does not own this conversation"),
        )
    return conv


def _message_count(db, conv_id: str) -> int:
    return db.query(Message).filter(Message.conversation_id == conv_id).count()


def _title_from_first_message(text: str) -> str:
    """First ~60 chars or first sentence."""
    text = text.strip()
    if not text:
        return "New conversation"
    # First sentence (up to . ! ?)
    match = re.search(r"^[^.!?]+[.!?]?", text)
    if match:
        first = match.group(0).strip()
        return first[:60] + ("..." if len(first) > 60 else "")
    return text[:60] + ("..." if len(text) > 60 else "")


# --- Endpoints ---


@app.get("/health")
async def health():
    """Health check (no auth)."""
    return {"status": "ok"}


# --- Settings (stub: backend uses Together AI, no user API key needed) ---


@app.get("/settings")
async def get_settings(uid: str = Depends(get_current_uid)):
    """Stub: always returns anthropic_key_set=true since backend uses Together AI."""
    return {"anthropic_key_set": True, "anthropic_key_preview": None}


@app.put("/settings/anthropic-key")
async def update_anthropic_key(body: AnthropicKeyRequest, uid: str = Depends(get_current_uid)):
    """Stub: no-op, backend uses Together AI."""
    return {"anthropic_key_set": True, "anthropic_key_preview": None}


@app.delete("/settings/anthropic-key", status_code=status.HTTP_204_NO_CONTENT)
async def delete_anthropic_key(uid: str = Depends(get_current_uid)):
    """Stub: no-op, backend uses Together AI."""
    pass


@app.get("/conversations")
async def list_conversations(uid: str = Depends(get_current_uid)):
    """List user's conversations, sorted by updated_at desc."""
    with get_db() as db:
        convs = (
            db.query(Conversation)
            .filter(Conversation.user_id == uid)
            .order_by(Conversation.updated_at.desc())
            .all()
        )
        return {
            "conversations": [
                {
                    "id": c.id,
                    "title": c.title,
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                    "message_count": _message_count(db, c.id),
                }
                for c in convs
            ],
        }


@app.post("/conversations", status_code=status.HTTP_201_CREATED)
async def create_conversation(uid: str = Depends(get_current_uid)):
    """Create a new conversation. Upsert user if first conversation."""
    with get_db() as db:
        _get_or_create_user(db, uid)
        conv_id = f"conv_{generate(size=21)}"
        conv = Conversation(id=conv_id, user_id=uid)
        db.add(conv)
        db.flush()
        return {
            "id": conv.id,
            "title": None,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
            "message_count": 0,
        }


@app.get("/conversations/{conv_id}/messages")
async def list_messages(conv_id: str, uid: str = Depends(get_current_uid)):
    """List messages for conversation, ordered by created_at."""
    with get_db() as db:
        conv = _ensure_conversation_owner(db, conv_id, uid)
        messages = (
            db.query(Message)
            .filter(Message.conversation_id == conv_id)
            .order_by(Message.created_at)
            .all()
        )
        return {
            "messages": [
                {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at}
                for m in messages
            ]
        }


@app.post("/conversations/{conv_id}/chat")
async def chat(conv_id: str, body: ChatRequest, uid: str = Depends(get_current_uid)):
    """Send message, get LLM response."""
    with get_db() as db:
        conv = _ensure_conversation_owner(db, conv_id, uid)
        user = _get_or_create_user(db, uid)

        # 1. Persist user message
        user_msg_id = f"msg_{generate(size=21)}"
        user_msg = Message(
            id=user_msg_id,
            conversation_id=conv_id,
            role="user",
            content=body.message,
        )
        db.add(user_msg)

        # 2. Set conversation title from first message if not yet set
        if conv.title is None:
            conv.title = _title_from_first_message(body.message)
        conv.updated_at = datetime.utcnow()

        # 3. Load conversation history (including the message we just added)
        db.flush()
        messages = (
            db.query(Message)
            .filter(Message.conversation_id == conv_id)
            .order_by(Message.created_at)
            .all()
        )
        history = [{"role": m.role, "content": m.content} for m in messages]

        # 4 & 5. Call Together AI
        model = user.adapter_id if user.adapter_id else None
        try:
            assistant_content = chat_completion(history, model=model)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=error_response("inference_error", str(e)),
            )

        # 6. Persist assistant message
        assistant_msg_id = f"msg_{generate(size=21)}"
        assistant_msg = Message(
            id=assistant_msg_id,
            conversation_id=conv_id,
            role="assistant",
            content=assistant_content,
        )
        db.add(assistant_msg)
        conv.updated_at = datetime.utcnow()

        return {
            "id": assistant_msg_id,
            "role": "assistant",
            "content": assistant_content,
            "created_at": assistant_msg.created_at,
        }


@app.delete("/conversations/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conv_id: str, uid: str = Depends(get_current_uid)):
    """Delete conversation and cascade messages."""
    with get_db() as db:
        conv = _ensure_conversation_owner(db, conv_id, uid)
        db.delete(conv)


@app.get("/user/model-status")
async def model_status(uid: str = Depends(get_current_uid)):
    """Check if user has a fine-tuned adapter."""
    with get_db() as db:
        user = db.query(User).filter(User.uid == uid).first()
        has_adapter = user is not None and user.adapter_id is not None
        adapter_version = user.adapter_version if user else 0
        return {
            "has_adapter": has_adapter,
            "adapter_version": adapter_version,
            "base_model": get_base_model(),
        }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
