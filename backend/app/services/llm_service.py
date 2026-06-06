import os
from typing import Optional

OPENAI_KEY = os.getenv("OPENAI_API_KEY")

def call_openai(prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 512) -> dict:
    """Call OpenAI API (if key available). Returns dict with `text` or raises.

    This is a minimal wrapper so the backend can use a hosted LLM.
    """
    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY not set in environment")

    try:
        import openai
    except Exception as e:
        raise RuntimeError("openai package not installed") from e

    openai.api_key = OPENAI_KEY
    resp = openai.ChatCompletion.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    # extract text
    text = None
    if resp and "choices" in resp and len(resp["choices"]) > 0:
        text = resp["choices"][0].get("message", {}).get("content") or resp["choices"][0].get("text")

    return {"raw": resp, "text": text}


def generate(prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 512) -> str:
    out = call_openai(prompt, model=model, max_tokens=max_tokens)
    return out["text"] if out else ""
