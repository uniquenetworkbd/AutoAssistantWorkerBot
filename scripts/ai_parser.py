"""Gemini-assisted discovery of login form selectors.

Only sanitized DOM metadata and an optional screenshot are sent to Gemini.
Credentials are resolved locally by the scraper and are never sent to the model.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import google.generativeai as genai


class AIParserError(RuntimeError):
    """Raised when Gemini cannot produce a valid selector set."""


def _clean_response(text: str) -> dict[str, str]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I | re.S).strip()
    try:
        payload: Any = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AIParserError("Gemini returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise AIParserError("Gemini returned a non-object response")

    result = {
        key: str(payload.get(key, "")).strip()
        for key in ("username_selector", "password_selector", "login_button_selector")
    }
    if not all(result.values()):
        raise AIParserError("Gemini did not return all required selectors")
    return result


def _sanitize_html(html: str) -> str:
    # Remove form values and common credential/token attributes before model submission.
    html = re.sub(r"\b(value|placeholder|data-token|data-password)\s*=\s*(['\"]).*?\2", r"\1=\2\2", html, flags=re.I | re.S)
    html = re.sub(r"<(script|style)\b.*?</\1>", "", html, flags=re.I | re.S)
    return html[:120_000]


def detect_login_selectors(html: str, screenshot_bytes: bytes | None = None) -> dict[str, str]:
    """Ask Gemini to identify robust CSS selectors for a login form."""
    api_key = os.getenv("AUTO_ASSISTANT_GEMINI_API_KEY")
    if not api_key:
        raise AIParserError("AUTO_ASSISTANT_GEMINI_API_KEY is not configured")

    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    model = genai.GenerativeModel(model_name)
    prompt = """You are a web-automation selector analyst.
Inspect the supplied login-page DOM and return ONLY valid JSON with exactly:
username_selector, password_selector, login_button_selector.
Use robust CSS selectors based on id, name, type, aria-label, or stable attributes.
Do not invent selectors and avoid fragile nth-child selectors where possible.
Never request, infer, or output credentials.

DOM:
""" + _sanitize_html(html)

    contents: list[Any] = [prompt]
    if screenshot_bytes:
        contents.append({"mime_type": "image/png", "data": screenshot_bytes})
    try:
        response = model.generate_content(contents)
        return _clean_response(response.text)
    except AIParserError:
        raise
    except Exception as exc:
        raise AIParserError(f"Gemini selector discovery failed: {exc}") from exc
