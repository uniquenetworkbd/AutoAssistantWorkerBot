"""AI-assisted login selector discovery.

Only DOM metadata/HTML is sent to Gemini. Credentials are never sent to the model.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import google.generativeai as genai


class AIParserError(RuntimeError):
    pass


def _clean_json(text: str) -> dict[str, str]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()
    data: Any = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Gemini returned a non-object response")
    result = {k: str(data.get(k, "")).strip() for k in ("username_selector", "password_selector", "login_button_selector")}
    if not all(result.values()):
        raise ValueError("Gemini did not return all required selectors")
    return result


def detect_login_selectors(html: str, screenshot_bytes: bytes | None = None) -> dict[str, str]:
    """Return CSS selectors for username, password and login button fields."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise AIParserError("GEMINI_API_KEY is not configured")

    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    model = genai.GenerativeModel(model_name)

    # Keep the prompt payload bounded; credentials/values are removed before sending.
    sanitized = re.sub(r'(value\s*=\s*["\']).*?(["\'])', r'\1\2', html, flags=re.I | re.S)
    sanitized = sanitized[:120_000]
    prompt = """
You are a web automation selector analyst. Inspect the supplied login-page DOM.
Return ONLY valid JSON with exactly these keys:
username_selector, password_selector, login_button_selector.
Selectors must be robust CSS selectors and should prefer id/name/type/aria-label over fragile nth-child selectors.
Do not invent selectors. If several choices exist, select the most likely visible login controls.
No credentials are present and none should be requested.
DOM:
""" + sanitized

    contents: list[Any] = [prompt]
    if screenshot_bytes:
        contents.append({"mime_type": "image/png", "data": screenshot_bytes})
    response = model.generate_content(contents)
    return _clean_json(response.text)
