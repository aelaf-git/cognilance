"""Minimal Groq helper for test agents."""

from __future__ import annotations

import os
import time

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

DEFAULT_MODEL = "llama-3.3-70b-versatile"

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Set GROQ_API_KEY in your .env file.")
        _client = Groq(api_key=api_key)
    return _client


def _default_model() -> str:
    return os.getenv("GROQ_MODEL", DEFAULT_MODEL)


def ask(system: str, prompt: str, *, model: str | None = None) -> str:
    client = _get_client()
    model_name = model or _default_model()

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            message = str(exc).lower()
            if "rate" in message or "429" in message:
                if attempt < 2:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise RuntimeError(
                    f"Groq rate limit hit for model '{model_name}'. "
                    "Wait a moment and retry, or set GROQ_MODEL in .env."
                ) from exc
            raise RuntimeError(f"Groq API error: {exc}") from exc

    raise RuntimeError("Groq request failed after retries.")
