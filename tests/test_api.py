"""API endpoint tests."""

import pytest
from unittest.mock import patch, AsyncMock

from tests.conftest import TEST_UID


class TestHealth:
    """GET /health - no auth required."""

    def test_health_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestConversations:
    """Conversation CRUD endpoints."""

    def test_create_conversation(self, client, auth_headers):
        r = client.post("/conversations", headers=auth_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["id"].startswith("conv_")
        assert data["title"] is None
        assert data["message_count"] == 0
        assert "created_at" in data
        assert "updated_at" in data

    def test_list_conversations_empty(self, client, auth_headers):
        r = client.get("/conversations", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == []

    def test_list_conversations_after_create(self, client, auth_headers):
        client.post("/conversations", headers=auth_headers)
        r = client.get("/conversations", headers=auth_headers)
        assert r.status_code == 200
        convs = r.json()
        assert len(convs) == 1
        assert convs[0]["id"].startswith("conv_")
        assert convs[0]["message_count"] == 0

    def test_conversations_require_auth(self, unauth_client):
        r = unauth_client.get("/conversations")
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "invalid_token"

    def test_create_requires_auth(self, unauth_client):
        r = unauth_client.post("/conversations")
        assert r.status_code == 401


class TestMessages:
    """GET /conversations/:id/messages."""

    def test_list_messages_empty(self, client, auth_headers):
        create = client.post("/conversations", headers=auth_headers)
        conv_id = create.json()["id"]
        r = client.get(f"/conversations/{conv_id}/messages", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == {"messages": []}

    def test_list_messages_404(self, client, auth_headers):
        r = client.get("/conversations/conv_nonexistent/messages", headers=auth_headers)
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "not_found"

    def test_list_messages_403_when_not_owner(self, conv_owned_by_test_user, other_user_client):
        """User B cannot access User A's conversation."""
        conv_id = conv_owned_by_test_user
        r = other_user_client.get(
            f"/conversations/{conv_id}/messages",
            headers={"Authorization": "Bearer fake"},
        )
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "forbidden"


class TestChat:
    """POST /conversations/:id/chat - send message, get LLM response."""

    @patch("main.chat_completion", new_callable=AsyncMock)
    def test_chat_returns_assistant_message(self, mock_chat, client, auth_headers):
        mock_chat.return_value = "Hello! How can I help?"
        create = client.post("/conversations", headers=auth_headers)
        conv_id = create.json()["id"]

        r = client.post(
            f"/conversations/{conv_id}/chat",
            headers=auth_headers,
            json={"message": "Hi there"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["id"].startswith("msg_")
        assert data["role"] == "assistant"
        assert data["content"] == "Hello! How can I help?"
        assert "created_at" in data

        mock_chat.assert_called_once()
        history = mock_chat.call_args[0][0]
        assert len(history) == 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hi there"

    @patch("main.chat_completion", new_callable=AsyncMock)
    def test_chat_sets_conversation_title_from_first_message(self, mock_chat, client, auth_headers):
        mock_chat.return_value = "Sure!"
        create = client.post("/conversations", headers=auth_headers)
        conv_id = create.json()["id"]

        client.post(
            f"/conversations/{conv_id}/chat",
            headers=auth_headers,
            json={"message": "What is the capital of France?"},
        )

        list_r = client.get("/conversations", headers=auth_headers)
        convs = list_r.json()
        assert len(convs) == 1
        assert convs[0]["title"] == "What is the capital of France?"

    @patch("main.chat_completion", new_callable=AsyncMock)
    def test_chat_404_for_missing_conversation(self, mock_chat, client, auth_headers):
        r = client.post(
            "/conversations/conv_nonexistent/chat",
            headers=auth_headers,
            json={"message": "Hi"},
        )
        assert r.status_code == 404
        mock_chat.assert_not_called()

    @patch("main.chat_completion", new_callable=AsyncMock)
    def test_chat_inference_error_returns_502(self, mock_chat, client, auth_headers):
        mock_chat.side_effect = Exception("Together API unavailable")
        create = client.post("/conversations", headers=auth_headers)
        conv_id = create.json()["id"]

        r = client.post(
            f"/conversations/{conv_id}/chat",
            headers=auth_headers,
            json={"message": "Hi"},
        )
        assert r.status_code == 502
        assert r.json()["error"]["code"] == "inference_error"


class TestDeleteConversation:
    """DELETE /conversations/:id."""

    def test_delete_conversation(self, client, auth_headers):
        create = client.post("/conversations", headers=auth_headers)
        conv_id = create.json()["id"]

        r = client.delete(f"/conversations/{conv_id}", headers=auth_headers)
        assert r.status_code == 204

        list_r = client.get("/conversations", headers=auth_headers)
        assert list_r.json() == []

    def test_delete_404(self, client, auth_headers):
        r = client.delete("/conversations/conv_nonexistent", headers=auth_headers)
        assert r.status_code == 404


class TestModelStatus:
    """GET /user/model-status."""

    def test_model_status_no_adapter(self, client, auth_headers):
        r = client.get("/user/model-status", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["has_adapter"] is False
        assert data["adapter_version"] == 0
        assert "base_model" in data

    def test_model_status_requires_auth(self, unauth_client):
        r = unauth_client.get("/user/model-status")
        assert r.status_code == 401
