"""One tiny provider-agnostic LLM call (plain `requests`, no SDKs)."""
import os
import sys
import time

import requests

DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5", "gemini": "gemini-flash-latest"}


def provider() -> str:
    p = os.getenv("LLM_PROVIDER", "").lower()
    if p:
        return p
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    raise RuntimeError("Set GEMINI_API_KEY or ANTHROPIC_API_KEY first.")


def model_name() -> str:
    return os.getenv("LLM_MODEL") or DEFAULT_MODELS[provider()]


def _post_with_retry(url, headers, body, tries=5):
    for attempt in range(tries):
        r = requests.post(url, headers=headers, json=body, timeout=180)
        if r.status_code in (429, 500, 502, 503, 529) and attempt < tries - 1:
            time.sleep(2 ** attempt * 2)
            continue
        if r.status_code >= 400:
            raise requests.HTTPError(f"{r.status_code}: {r.text[:400]}", response=r)
        return r.json()


def complete(system: str, user: str, max_tokens: int = 3000, temperature: float = 0.1, json_mode: bool = False) -> str:
    p, m = provider(), model_name()
    if p == "anthropic":
        data = _post_with_retry(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
            {"model": m, "max_tokens": max_tokens, "temperature": temperature,
             "system": system, "messages": [{"role": "user", "content": user}]},
        )
        return "".join(b.get("text", "") for b in data["content"])
    if p == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
        headers = {"x-goog-api-key": os.environ["GEMINI_API_KEY"]}
        # settings from strongest to safest; if Gemini rejects one (400), fall back to the next
        attempts = [
            {"temperature": temperature, "maxOutputTokens": 16384, **({"responseMimeType": "application/json"} if json_mode else {})},
            {"temperature": temperature, "maxOutputTokens": 8192},
            {},
        ]
        last = None
        for cfg in attempts:
            body = {"systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": user}]}]}
            if cfg:
                body["generationConfig"] = cfg
            try:
                data = _post_with_retry(url, headers, body)
                parts = data["candidates"][0]["content"]["parts"]
                return "".join(x.get("text", "") for x in parts if not x.get("thought"))
            except requests.HTTPError as e:
                last = e
                print(f"  [gemini rejected settings {cfg}: {e}]", file=sys.stderr)
                if "400" not in str(e)[:5]:
                    raise
        raise last
    raise RuntimeError(f"Unknown provider {p}")