# Navigator Chat — Backend API Spec (v2)

Backend for the Navigator Chat frontend. Runs on **localhost:8000** (or configurable port).

**Frontend spec (API contract):** [navigator-chat-app-spec.md](./navigator-chat-app-spec.md)

---

## Goal

- Serve the REST API at `http://localhost:8000` (or `PORT` env).
- Verify Firebase ID tokens and scope all data by user.
- Store conversations and messages in SQLite.
- Handle chat by calling **Together AI** inference (base model or user's LoRA adapter).
- Persist all conversation data for downstream fine-tuning (Phase 2).

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Runtime | **Python + FastAPI** |
| Auth | Firebase Admin SDK (token verification) |
| Database | **SQLite** (single file, zero config) |
| LLM Provider | **Together AI** (OpenAI-compatible API) |
| CORS | Allow frontend origin |

---

## Environment variables

```
PORT=8000
DATABASE_PATH=./navigator.db          # SQLite file path

# Firebase
FIREBASE_PROJECT_ID=your-project-id

# Together AI
TOGETHER_API_KEY=your-together-api-key
TOGETHER_MODEL=meta-llama/Llama-3-8B-Instruct  # base model for new users
```

No user-provided API keys. The platform provides inference via a single Together AI account. Users chat; Navigator handles the rest.

---

## Auth (every request)

1. Read `Authorization: Bearer <token>`.
2. If missing or invalid → **401** `invalid_token`.
3. Verify the token with Firebase Admin and extract **uid**.
4. Attach **uid** to the request context for all DB lookups.

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check (no auth) |
| GET | /conversations | List user's conversations |
| POST | /conversations | Create conversation |
| GET | /conversations/:id/messages | List messages for conversation |
| POST | /conversations/:id/chat | Send message, get response |
| DELETE | /conversations/:id | Delete conversation |
| GET | /user/model-status | Check if user has a fine-tuned adapter |

All responses are JSON except **204** (no content).

---

## Error response format

```json
{
  "error": {
    "code": "<code>",
    "message": "<human-readable message>"
  }
}
```

| HTTP | code | When |
|------|------|------|
| 401 | invalid_token | Missing/expired/invalid Firebase token |
| 403 | forbidden | User does not own this conversation |
| 404 | not_found | Conversation not found |
| 429 | rate_limited | Too many requests (optional for beta) |
| 500 | internal_error | Unexpected server error |
| 502 | inference_error | Together AI returned an error |

---

## Data model

### Tables

**users**
| Column | Type | Notes |
|--------|------|-------|
| uid | TEXT PK | Firebase UID |
| adapter_id | TEXT | Together AI adapter ID (null = use base model) |
| adapter_version | INTEGER | Incremented on each fine-tune |
| created_at | DATETIME | |
| updated_at | DATETIME | |

**conversations**
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | Prefixed: `conv_xxx` |
| user_id | TEXT FK | References users.uid |
| title | TEXT | Nullable, set from first message |
| created_at | DATETIME | |
| updated_at | DATETIME | |

**messages**
| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | Prefixed: `msg_xxx` |
| conversation_id | TEXT FK | References conversations.id |
| role | TEXT | `user` or `assistant` |
| content | TEXT | |
| created_at | DATETIME | |

IDs: use `nanoid` with `conv_` / `msg_` prefixes.

---

## Endpoint details

### GET /health
- No auth required.
- Return `{ "status": "ok" }`.

### GET /conversations
- Auth required.
- Return list of conversations for authenticated user.
- Each: `id`, `title`, `created_at`, `updated_at`, `message_count`.
- Sorted by `updated_at` descending.

### POST /conversations
- Auth required.
- Create a new conversation (no body needed).
- Upsert user record if first conversation.
- Return **201** with conversation object: `{ id, title: null, created_at, updated_at, message_count: 0 }`.

### GET /conversations/:id/messages
- 404 if conversation missing, 403 if not owner.
- Return `{ "messages": [...] }` ordered by `created_at`.

### POST /conversations/:id/chat
- Body: `{ "message": "user text" }`.
- 404 if conversation missing, 403 if not owner.
- Flow:
  1. Persist user message.
  2. Set conversation title from first message if not yet set (first ~60 chars or first sentence).
  3. Load conversation history.
  4. Check if user has `adapter_id` in users table.
  5. Call Together AI inference:
     - If adapter exists: use base model + adapter via `model` param (Together's multi-LoRA serving).
     - If no adapter: use base model from `TOGETHER_MODEL` env var.
  6. Persist assistant message.
  7. Update conversation `updated_at`.
  8. Return `{ id, role: "assistant", content, created_at }`.

### DELETE /conversations/:id
- 404 if not found, 403 if not owner.
- Delete conversation and cascade messages.
- Return **204**.

### GET /user/model-status
- Auth required.
- Return `{ "has_adapter": true|false, "adapter_version": 3, "base_model": "meta-llama/..." }`.
- This powers the frontend's personalization indicator.

---

## Together AI integration

### Inference (chat)

Together AI supports OpenAI-compatible chat completions. Use the OpenAI SDK pointed at Together's base URL:

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["TOGETHER_API_KEY"],
    base_url="https://api.together.xyz/v1"
)

# For base model users:
model = os.environ["TOGETHER_MODEL"]

# For users with a LoRA adapter:
# Together serves LoRA adapters on-demand via the same endpoint
# The adapter_id from fine-tuning IS the model identifier
model = user.adapter_id  # e.g. "user-abc123-v3"

response = client.chat.completions.create(
    model=model,
    messages=conversation_history,
    max_tokens=1024
)
```

### System prompt

Use a minimal system prompt for the base model:

```
You are a helpful assistant.
```

The whole point is that fine-tuning replaces the need for elaborate prompting. The model learns the user's preferences through weight updates, not system prompt instructions.

---

## CORS

Allow the frontend origin:

- Origin: `http://localhost:5173` (and `http://127.0.0.1:5173`)
- Methods: GET, POST, DELETE
- Headers: `Content-Type`, `Authorization`

---

## What this backend does NOT do

This is the **chat backend only**. The following are separate services built in later phases:

- **Ingestion worker** (Phase 2): Reads from this same SQLite DB, exports JSONL training files.
- **Fine-tune orchestrator** (Phase 3): Calls Together fine-tuning API, updates `users.adapter_id`.
- **Visualization dashboard** (Phase 4): Reads from DB + adapter registry.

The chat backend just needs to check `users.adapter_id` and route inference accordingly. Everything else is decoupled.

---

## Implementation steps

1. Create `backend/` directory. Init Python project with FastAPI, uvicorn, firebase-admin, openai.
2. Set up SQLite with the three tables above (use raw SQL or SQLModel/SQLAlchemy).
3. Implement Firebase auth middleware.
4. Implement endpoints per this spec.
5. Add CORS middleware.
6. Add README with: env vars, how to run (`uvicorn main:app --port 8000`).
7. Test: start backend on 8000, start frontend on 5173, sign in, create conversation, send message.

**Done when:** Frontend can sign in, create conversations, send messages, and receive responses from Together AI via this backend.
