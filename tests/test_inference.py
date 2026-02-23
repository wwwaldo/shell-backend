"""Tests for Together AI inference client."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from inference import chat_completion, get_base_model


class TestGetBaseModel:
    def test_returns_default_model(self):
        assert get_base_model() == "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"


class TestChatCompletion:
    @pytest.mark.asyncio
    @patch("inference.get_together_client")
    async def test_chat_returns_content(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello!"
        mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await chat_completion([{"role": "user", "content": "Hi"}], model=None)
        assert result == "Hello!"

    @pytest.mark.asyncio
    @patch("inference.get_together_client")
    async def test_chat_uses_user_adapter_when_provided(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Personalized"
        mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)

        await chat_completion([{"role": "user", "content": "Hi"}], model="user-abc123-v3")
        mock_client.return_value.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.return_value.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "user-abc123-v3"
