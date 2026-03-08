"""Multi-provider LLM service with streaming support."""
import json
import logging
from typing import AsyncGenerator, Optional, Dict, List

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

# Provider configurations
PROVIDERS: Dict[str, dict] = {
    "anthropic": {
        "name": "Anthropic (Claude)",
        "base_url": "https://api.anthropic.com/v1",
        "models": [
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "max_tokens": 8192},
            {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5", "max_tokens": 8192},
            {"id": "claude-opus-4-6", "name": "Claude Opus 4.6", "max_tokens": 8192},
        ],
    },
    "openai": {
        "name": "OpenAI (GPT)",
        "base_url": "https://api.openai.com/v1",
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o", "max_tokens": 4096},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "max_tokens": 4096},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "max_tokens": 4096},
        ],
    },
    "google": {
        "name": "Google (Gemini)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "models": [
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "max_tokens": 8192},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "max_tokens": 8192},
        ],
    },
}


def get_api_key(provider: str) -> Optional[str]:
    key_map = {
        "anthropic": settings.ANTHROPIC_API_KEY,
        "openai": settings.OPENAI_API_KEY,
        "google": settings.GOOGLE_API_KEY,
    }
    return key_map.get(provider)


def get_available_providers() -> List[dict]:
    result = []
    for pid, pconfig in PROVIDERS.items():
        result.append({
            "id": pid,
            "name": pconfig["name"],
            "available": get_api_key(pid) is not None,
            "models": pconfig["models"],
        })
    return result


async def stream_anthropic(
    messages: List[dict],
    model: str,
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> AsyncGenerator[str, None]:
    """Stream from Anthropic Claude API."""
    api_key = get_api_key("anthropic")
    if not api_key:
        yield json.dumps({"type": "error", "content": "Anthropic API key not configured"})
        return

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
        "messages": messages,
    }
    if system_prompt:
        body["system"] = system_prompt

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            async with client.stream(
                "POST",
                f"{PROVIDERS['anthropic']['base_url']}/messages",
                headers=headers,
                json=body,
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    yield json.dumps({"type": "error", "content": f"API error {response.status_code}: {error_body.decode()}"})
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                        event_type = event.get("type", "")

                        if event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield json.dumps({"type": "text", "content": delta["text"]})

                        elif event_type == "message_stop":
                            yield json.dumps({"type": "done"})

                        elif event_type == "error":
                            yield json.dumps({"type": "error", "content": event.get("error", {}).get("message", "Unknown error")})

                    except json.JSONDecodeError:
                        continue
        except httpx.HTTPError as e:
            logger.error(f"Anthropic stream error: {e}")
            yield json.dumps({"type": "error", "content": str(e)})


async def stream_openai(
    messages: List[dict],
    model: str,
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> AsyncGenerator[str, None]:
    """Stream from OpenAI API."""
    api_key = get_api_key("openai")
    if not api_key:
        yield json.dumps({"type": "error", "content": "OpenAI API key not configured"})
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    oai_messages = []
    if system_prompt:
        oai_messages.append({"role": "system", "content": system_prompt})
    oai_messages.extend(messages)

    body = {
        "model": model,
        "messages": oai_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            async with client.stream(
                "POST",
                f"{PROVIDERS['openai']['base_url']}/chat/completions",
                headers=headers,
                json=body,
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    yield json.dumps({"type": "error", "content": f"API error {response.status_code}: {error_body.decode()}"})
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        yield json.dumps({"type": "done"})
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield json.dumps({"type": "text", "content": content})
                    except json.JSONDecodeError:
                        continue
        except httpx.HTTPError as e:
            logger.error(f"OpenAI stream error: {e}")
            yield json.dumps({"type": "error", "content": str(e)})


async def stream_google(
    messages: List[dict],
    model: str,
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> AsyncGenerator[str, None]:
    """Stream from Google Gemini API."""
    api_key = get_api_key("google")
    if not api_key:
        yield json.dumps({"type": "error", "content": "Google API key not configured"})
        return

    # Convert messages to Gemini format
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    body = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_prompt:
        body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    url = f"{PROVIDERS['google']['base_url']}/models/{model}:streamGenerateContent?alt=sse&key={api_key}"

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            async with client.stream("POST", url, json=body) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    yield json.dumps({"type": "error", "content": f"API error {response.status_code}: {error_body.decode()}"})
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    try:
                        chunk = json.loads(data)
                        candidates = chunk.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for part in parts:
                                text = part.get("text", "")
                                if text:
                                    yield json.dumps({"type": "text", "content": text})
                    except json.JSONDecodeError:
                        continue

            yield json.dumps({"type": "done"})
        except httpx.HTTPError as e:
            logger.error(f"Google stream error: {e}")
            yield json.dumps({"type": "error", "content": str(e)})


async def stream_chat(
    provider: str,
    messages: List[dict],
    model: str,
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> AsyncGenerator[str, None]:
    """Route to the appropriate provider's streaming function."""
    stream_map = {
        "anthropic": stream_anthropic,
        "openai": stream_openai,
        "google": stream_google,
    }

    stream_fn = stream_map.get(provider)
    if not stream_fn:
        yield json.dumps({"type": "error", "content": f"Unknown provider: {provider}"})
        return

    async for chunk in stream_fn(messages, model, system_prompt, temperature, max_tokens):
        yield chunk
