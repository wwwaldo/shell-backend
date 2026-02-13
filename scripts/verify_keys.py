#!/usr/bin/env python3
"""Verify API keys are valid. Run from project root: python scripts/verify_keys.py"""

import os
import sys

# Load .env before imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

def verify_together():
    """Test Together AI key with a minimal chat request."""
    api_key = os.environ.get("TOGETHER_API_KEY")
    if not api_key:
        print("❌ TOGETHER_API_KEY not set in .env")
        return False
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.together.xyz/v1")
        from inference import DEFAULT_MODEL
        model = DEFAULT_MODEL
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say 'ok' and nothing else."}],
            max_tokens=10,
        )
        content = resp.choices[0].message.content if resp.choices else ""
        print(f"✅ Together AI: key valid (model={model}, response='{content.strip()}')")
        return True
    except Exception as e:
        err = str(e)
        if "401" in err or "authentication" in err.lower():
            print(f"❌ Together AI: invalid API key")
            return False
        if "model_not_available" in err or "404" in err or "model" in err.lower():
            print(f"❌ Together AI: model not found (check DEFAULT_MODEL in inference.py)")
            print(f"   See https://api.together.xyz/v1/models for available models")
            print(f"   Error: {e}")
            return False
        print(f"❌ Together AI: {e}")
        return False

def verify_firebase():
    """Firebase is validated per-request when verifying tokens. No standalone check."""
    project_id = os.environ.get("FIREBASE_PROJECT_ID")
    creds = os.environ.get("FIREBASE_CREDENTIALS_PATH") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not project_id:
        print("⚠️  FIREBASE_PROJECT_ID not set (auth will fail)")
        return False
    if not creds or not os.path.isfile(creds):
        print("⚠️  Firebase credentials file not found (FIREBASE_CREDENTIALS_PATH or GOOGLE_APPLICATION_CREDENTIALS)")
        return False
    print("✅ Firebase: project_id and credentials path set (validated on first token)")
    return True

if __name__ == "__main__":
    print("Verifying API keys...\n")
    t = verify_together()
    f = verify_firebase()
    print()
    sys.exit(0 if t else 1)
