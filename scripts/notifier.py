"""Telegram delivery and persistent error logging."""
from __future__ import annotations

import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
ERROR_LOG = ROOT / "memory" / "error_log.json"


def _append_error(context: str, exc: BaseException) -> None:
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(ERROR_LOG.read_text(encoding="utf-8")) if ERROR_LOG.exists() else []
        if not isinstance(data, list):
            data = []
    except Exception:
        data = []
    data.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "context": context,
        "error": str(exc),
        "traceback": traceback.format_exc(limit=8),
    })
    ERROR_LOG.write_text(json.dumps(data[-200:], indent=2, ensure_ascii=False), encoding="utf-8")


def _telegram(method: str, **kwargs: Any) -> dict[str, Any]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")
    url = f"https://api.telegram.org/bot{token}/{method}"
    response = requests.post(url, **kwargs, timeout=45)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API error: {payload}")
    return payload


def send_document(path: Path, caption: str = "AutoAssistantWorkerBot report") -> None:
    try:
        with path.open("rb") as fh:
            _telegram("sendDocument", data={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "caption": caption[:1024]}, files={"document": (path.name, fh)})
    except Exception as exc:
        _append_error("send_document", exc)
        raise


def send_alert(message: str) -> None:
    try:
        _telegram("sendMessage", data={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": message[:4096]})
    except Exception as exc:
        _append_error("send_alert", exc)
        # Alert failure must not mask the original workflow exception.
