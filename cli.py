#!/usr/bin/env python3
"""
CLI frontend for Navigator Chat backend. Verifies API functionality.

Usage:
  # Dev mode (no Firebase): set DEV_MODE=1 in backend .env, then:
  python cli.py --dev health
  python cli.py --dev list
  python cli.py --dev chat "Hello, what's 2+2?"

  # With Firebase token (from web app):
  NAVIGATOR_TOKEN=<id-token> python cli.py list
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import requests

# Load .env for NAVIGATOR_TOKEN, NAVIGATOR_API_URL
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DEFAULT_BASE_URL = os.environ.get("NAVIGATOR_API_URL", "http://localhost:8000")
DEV_UID = "cli-dev-user"


def get_headers(dev: bool, token: str | None) -> dict[str, str]:
    if dev:
        return {"X-Dev-User-Id": DEV_UID}
    if token:
        return {"Authorization": f"Bearer {token}"}
    token = os.environ.get("NAVIGATOR_TOKEN")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def req(
    method: str,
    path: str,
    base_url: str,
    headers: dict,
    json_body: dict | None = None,
) -> requests.Response:
    url = f"{base_url.rstrip('/')}{path}"
    return requests.request(method, url, headers=headers, json=json_body, timeout=30)


def cmd_health(base_url: str, _headers: dict) -> int:
    r = req("GET", "/health", base_url, {})
    if r.status_code != 200:
        print(f"Health check failed: {r.status_code}", file=sys.stderr)
        return 1
    data = r.json()
    print(json.dumps(data, indent=2))
    return 0


def cmd_conversations_list(base_url: str, headers: dict) -> int:
    r = req("GET", "/conversations", base_url, headers)
    if r.status_code != 200:
        print_err(r)
        return 1
    convs = r.json()
    if not convs:
        print("No conversations.")
        return 0
    for c in convs:
        title = (c.get("title") or "(no title)")[:50]
        print(f"  {c['id']}  {title}  ({c.get('message_count', 0)} msgs)")
    return 0


def cmd_conversations_create(base_url: str, headers: dict) -> int:
    r = req("POST", "/conversations", base_url, headers)
    if r.status_code != 201:
        print_err(r)
        return 1
    data = r.json()
    print(f"Created: {data['id']}")
    return 0


def cmd_messages(base_url: str, headers: dict, conv_id: str) -> int:
    r = req("GET", f"/conversations/{conv_id}/messages", base_url, headers)
    if r.status_code != 200:
        print_err(r)
        return 1
    data = r.json()
    for m in data.get("messages", []):
        role = m["role"].upper()
        content = (m["content"] or "")[:200]
        print(f"  [{role}] {content}")
    return 0


def cmd_chat(base_url: str, headers: dict, message: str, conv_id: str | None) -> int:
    if not conv_id:
        # Create conversation first
        r = req("POST", "/conversations", base_url, headers)
        if r.status_code != 201:
            print_err(r)
            return 1
        conv_id = r.json()["id"]
        print(f"Created conversation {conv_id}")

    r = req("POST", f"/conversations/{conv_id}/chat", base_url, headers, {"message": message})
    if r.status_code != 200:
        print_err(r)
        return 1
    data = r.json()
    print(f"[ASSISTANT] {data['content']}")
    return 0


def cmd_delete(base_url: str, headers: dict, conv_id: str) -> int:
    r = req("DELETE", f"/conversations/{conv_id}", base_url, headers)
    if r.status_code != 204:
        print_err(r)
        return 1
    print("Deleted.")
    return 0


def cmd_model_status(base_url: str, headers: dict) -> int:
    r = req("GET", "/user/model-status", base_url, headers)
    if r.status_code != 200:
        print_err(r)
        return 1
    data = r.json()
    print(json.dumps(data, indent=2))
    return 0


def print_err(r: requests.Response) -> None:
    try:
        data = r.json()
        err = data.get("error", {})
        print(f"Error {r.status_code}: {err.get('code', '?')} - {err.get('message', r.text)}", file=sys.stderr)
    except Exception:
        print(f"Error {r.status_code}: {r.text}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Navigator Chat CLI - verify backend functionality",
        epilog="Dev mode: set DEV_MODE=1 in backend .env, then use --dev",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL")
    parser.add_argument("--dev", action="store_true", help="Use dev mode (no Firebase), requires DEV_MODE=1 on backend")
    parser.add_argument("--token", help="Firebase ID token (or set NAVIGATOR_TOKEN)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="Health check")
    sub.add_parser("list", help="List conversations")
    sub.add_parser("create", help="Create a conversation")
    sub.add_parser("model-status", help="Check user model/adapter status")

    msg_parser = sub.add_parser("messages", help="List messages in a conversation")
    msg_parser.add_argument("conv_id", help="Conversation ID")

    chat_parser = sub.add_parser("chat", help="Send a message (creates conv if needed)")
    chat_parser.add_argument("message", help="Message to send")
    chat_parser.add_argument("--conv", help="Conversation ID (creates new if omitted)")

    del_parser = sub.add_parser("delete", help="Delete a conversation")
    del_parser.add_argument("conv_id", help="Conversation ID to delete")

    args = parser.parse_args()
    headers = get_headers(args.dev, args.token)

    if not args.dev and not headers:
        print("Error: Use --dev (set DEV_MODE=1 in backend .env) or provide --token / NAVIGATOR_TOKEN", file=sys.stderr)
        return 1

    base_url = args.base_url

    if args.command == "health":
        return cmd_health(base_url, headers)
    if args.command == "list":
        return cmd_conversations_list(base_url, headers)
    if args.command == "create":
        return cmd_conversations_create(base_url, headers)
    if args.command == "messages":
        return cmd_messages(base_url, headers, args.conv_id)
    if args.command == "chat":
        return cmd_chat(base_url, headers, args.message, getattr(args, "conv", None))
    if args.command == "delete":
        return cmd_delete(base_url, headers, args.conv_id)
    if args.command == "model-status":
        return cmd_model_status(base_url, headers)

    return 1


if __name__ == "__main__":
    sys.exit(main())
