"""Together AI inference client."""

from __future__ import annotations

import os
from typing import Optional

from openai import AsyncOpenAI

TOGETHER_BASE_URL = "https://api.together.xyz/v1"
SYSTEM_PROMPT = "You are a helpful assistant."

# Base model for users without a fine-tuned adapter
# See https://docs.together.ai/docs/serverless-models
DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"


def get_together_client() -> AsyncOpenAI:
    api_key = os.environ.get("TOGETHER_API_KEY")
    if not api_key:
        raise RuntimeError("TOGETHER_API_KEY environment variable is required")
    return AsyncOpenAI(api_key=api_key, base_url=TOGETHER_BASE_URL)


def get_base_model() -> str:
    return DEFAULT_MODEL


async def chat_completion(
    messages: list[dict[str, str]],
    model: Optional[str] = None,
) -> str:
    """
    Call Together AI chat completions.
    messages: list of {"role": "user"|"assistant"|"system", "content": "..."}
    model: base model or user's adapter_id. If None, uses DEFAULT_MODEL.
    """
    client = get_together_client()
    model = model or get_base_model()

    # Prepend system prompt if not already present
    formatted = []
    if messages and messages[0].get("role") != "system":
        formatted.append({"role": "system", "content": SYSTEM_PROMPT})
    formatted.extend(messages)

    response = await client.chat.completions.create(
        model=model,
        messages=formatted,
        max_tokens=1024,
    )
    choice = response.choices[0] if response.choices else None
    if not choice or not choice.message:
        return ""
    return choice.message.content or ""
