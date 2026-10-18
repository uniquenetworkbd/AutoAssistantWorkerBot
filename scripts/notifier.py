"""Telegram reporting and persistent execution-error logging."""
from __future__ import annotations

import json
import os
import re
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
ERROR_LOG = ROOT / "memory" / "error_log.json"
WEBAPP_URL = os.getenv(
    "AUTO_ASSISTANT_WEBAPP_URL",
    "https://uniquenetworkbd.github.io/AutoAssistantWorkerBot/add-target/",
)

# Credentials can leak through exception strings, request URLs, tracebacks, or
# API error payloads. Keep this sanitizer local to the persistence boundary.
_SENSITIVE_PATTERNS = (
    (re.compile(r"https?://api\.telegram\.org/bot\d+:[A-Za-z0-9_-]{20,}", re.I), "https://api.telegram.org/bot[REDACTED]"),
    (re.compile(r"\bbot\d+:[A-Za-z0-9_-]{20,}\b", re.I), "bot[REDACTED]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.I), "Bearer [REDACTED]"),
    (re.compile(r"(?i)(token|secret|password|api[_-]?key|authorization)\s*([:=])\s*[\"']?[^\s,;\"'}]+"), r"\1\2 [REDACTED]"),
)


def _sanitize_text(value: Any) -> str:
    text = str(value or "")
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _sanitize_value(value: Any) -> Any:
    """Recursively sanitize strings so old and new log entries stay safe."""
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_value(item) for key, item in value.items()}
    return value


def record_error(stage: str, exc: BaseException, *, site_key: str | None = None, url: str | None = None) -> None:
    """Persist a bounded, credential-free execution error entry."""
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(ERROR_LOG.read_text(encoding="utf-8")) if ERROR_LOG.exists() else []
        if not isinstance(data, list):
            data = []
    except Exception:
        data = []

    # Sanitize existing entries as well, so a newly executed run repairs any
    # sensitive strings that may have been written by an older logger version.
    data = _sanitize_value(data)
    data.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": _sanitize_text(stage),
        "site_key": _sanitize_text(site_key) if site_key is not None else None,
        "url": _sanitize_text(url) if url is not None else None,
        "error": _sanitize_text(exc),
        "traceback": _sanitize_text(traceback.format_exc(limit=8)),
    })

    temporary = ERROR_LOG.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(data[-200:], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(ERROR_LOG)


def _telegram(method: str, **kwargs: Any) -> dict[str, Any]:
    token = os.getenv("AUTO_ASSISTANT_BOT_TOKEN")
    chat_id = os.getenv("AUTO_ASSISTANT_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("AUTO_ASSISTANT_BOT_TOKEN and AUTO_ASSISTANT_CHAT_ID are required")
    response = requests.post(
        f"https://api.telegram.org/bot{token}/{method}",
        **kwargs,
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API error: {payload}")
    return payload


def _add_target_keyboard() -> dict[str, Any]:
    return {
        "keyboard": [[{
            "text": "/add_target",
            "web_app": {"url": WEBAPP_URL},
        }]],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def send_report(report: dict[str, Any]) -> None:
    """Send a compact human-readable report plus JSON details to Telegram."""
    summary = (
        f"AutoAssistantWorkerBot — {report.get('status', 'unknown').upper()}\n"
        f"Run: {report.get('run_id', 'unknown')}\n"
        f"Targets: {report.get('target_count', 0)} | "
        f"Success: {report.get('success_count', 0)} | "
        f"Failed: {report.get('failure_count', 0)}"
    )
    details = json.dumps(report, indent=2, ensure_ascii=False)
    _telegram(
        "sendMessage",
        data={
            "chat_id": chat_id(),
            "text": summary,
            "reply_markup": json.dumps(_add_target_keyboard()),
        },
    )
    # Telegram messages are limited to 4096 characters.
    for offset in range(0, len(details), 3900):
        _telegram(
            "sendMessage",
            data={"chat_id": chat_id(), "text": details[offset : offset + 3900]},
        )


def chat_id() -> str:
    value = os.getenv("AUTO_ASSISTANT_CHAT_ID", "")
    if not value:
        raise RuntimeError("AUTO_ASSISTANT_CHAT_ID is required")
    return value


def send_alert(message: str) -> None:
    """Send an alert without masking the original workflow failure."""
    try:
        _telegram("sendMessage", data={"chat_id": chat_id(), "text": message[:4096]})
    except Exception as exc:
        record_error("telegram_alert", exc)
