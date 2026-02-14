# Navigator Chat Backend

REST API backend for the Navigator Chat frontend. Serves conversations and chat via Together AI inference.

## Environment variables

Create a `.env` file in the project root (it's gitignored) or export these before running:

| Variable | Description |
|----------|-------------|
| `PORT` | Server port (default: 8000) |
| `DATABASE_PATH` | SQLite file path (default: `./navigator.db`) |
| `FIREBASE_PROJECT_ID` | Firebase project ID (required for auth) |
| `TOGETHER_API_KEY` | Together AI API key (required for inference) |
| `DEV_MODE` | Set to `1` to allow CLI dev auth (X-Dev-User-Id), local testing only |

### Firebase setup

Firebase Admin SDK needs credentials. Use one of:

1. **Service account JSON**: Set `FIREBASE_CREDENTIALS_PATH` or `GOOGLE_APPLICATION_CREDENTIALS` to the path of your Firebase service account JSON file.
2. **gcloud default**: Run `gcloud auth application-default login` to use your user credentials.

## Docker

```bash
# Build and run locally
docker build -t navigator-backend .
docker run -p 8000:8000 -e FIREBASE_PROJECT_ID=... -e TOGETHER_API_KEY=... navigator-backend
```

See [DEPLOYMENT.md](./DEPLOYMENT.md) for GCP Cloud Run deployment.

## Run

```bash
# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Start the server
uvicorn main:app --port 8000
```

Or with auto-reload during development:

```bash
uvicorn main:app --port 8000 --reload
```

Or run directly:

```bash
python main.py
```

## API

- `GET /health` — Health check (no auth)
- `GET /conversations` — List conversations
- `POST /conversations` — Create conversation
- `GET /conversations/:id/messages` — List messages
- `POST /conversations/:id/chat` — Send message, get response
- `DELETE /conversations/:id` — Delete conversation
- `GET /user/model-status` — Check if user has fine-tuned adapter

All endpoints except `/health` require `Authorization: Bearer <Firebase ID token>`.

## Test

```bash
# Run all tests (no Firebase or Together API keys needed)
pytest

# With coverage
pytest --cov=. --cov-report=term-missing
```

Tests use mocked auth and inference, and an in-memory SQLite database.

## CLI (verify without frontend)

A CLI exercises the API for local verification:

```bash
# 1. Add DEV_MODE=1 to .env (bypasses Firebase for local testing)
# 2. Start backend: uvicorn main:app --port 8000
# 3. Run CLI:
python cli.py --dev health
python cli.py --dev list
python cli.py --dev create
python cli.py --dev chat "What is 2+2?"
python cli.py --dev model-status
```

With a real Firebase token: `NAVIGATOR_TOKEN=<id-token> python cli.py list`

## Manual test (with frontend)

1. Start backend: `uvicorn main:app --port 8000`
2. Start frontend on port 5173
3. Sign in, create a conversation, send a message
