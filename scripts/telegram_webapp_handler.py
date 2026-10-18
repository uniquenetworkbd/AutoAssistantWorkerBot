"""Secure Telegram WebApp receiver for the JSON-first target registry.

This receiver runs as a short-lived GitHub Actions worker. It polls Telegram
getUpdates, validates Telegram WebApp initData with HMAC-SHA-256, restricts
writes to the configured admin user, and updates input/targets.json through
the GitHub Contents API using the repository admin token.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

import requests

ROOT = Path(__file__).resolve().parents[1]
TARGETS_PATH = ROOT / "input" / "targets.json"
STATE_PATH = ROOT / "memory" / "webapp_state.json"
REPO = os.getenv("GITHUB_REPOSITORY", "uniquenetworkbd/AutoAssistantWorkerBot")
BRANCH = "main"
ADMIN_USER_ID = "5519303439"
MAX_AUTH_AGE = 24 * 60 * 60
ALLOWED_EXTRACTS = {"text", "html", "links"}
API = "https://api.github.com"


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def telegram_api(method: str, token: str, **kwargs: Any) -> dict[str, Any]:
    response = requests.post(
        f"https://api.telegram.org/bot{token}/{method}",
        **kwargs,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API error: {payload}")
    return payload


def validate_init_data(init_data: str, bot_token: str) -> dict[str, str]:
    """Validate Telegram WebApp initData and return its parsed fields."""
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", "")
    if not received_hash or len(received_hash) != 64:
        raise ValueError("Invalid Telegram WebApp hash")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    calculated = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        raise ValueError("Telegram WebApp signature validation failed")

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError as exc:
        raise ValueError("Invalid auth_date") from exc
    now = int(time.time())
    if auth_date <= 0 or auth_date > now + 300 or now - auth_date > MAX_AUTH_AGE:
        raise ValueError("Telegram WebApp authorization data is expired")

    user_raw = pairs.get("user", "")
    if not user_raw:
        raise ValueError("Telegram WebApp user data is missing")
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid Telegram user payload") from exc
    user_id = str(user.get("id", ""))
    if user_id != ADMIN_USER_ID:
        raise PermissionError("Telegram user is not authorized")

    return pairs


def load_state() -> dict[str, int]:
    if not STATE_PATH.exists():
        return {"last_update_id": 0}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return {"last_update_id": int(data.get("last_update_id", 0))}
    except Exception:
        return {"last_update_id": 0}


def save_state(last_update_id: int) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps({"last_update_id": last_update_id}, indent=2),
        encoding="utf-8",
    )


def github_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AutoAssistantWorkerBot-TelegramWebApp",
    }


def github_get_targets(token: str) -> tuple[list[dict[str, Any]], str]:
    url = f"{API}/repos/{REPO}/contents/{TARGETS_PATH.relative_to(ROOT).as_posix()}"
    response = requests.get(url, headers=github_headers(token), params={"ref": BRANCH}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    content = base64.b64decode(payload["content"]).decode("utf-8")
    data = json.loads(content)
    if not isinstance(data, list):
        raise ValueError("input/targets.json must contain a JSON array")
    return data, payload["sha"]


def github_update_targets(token: str, targets: list[dict[str, Any]], sha: str) -> str:
    path = TARGETS_PATH.relative_to(ROOT).as_posix()
    url = f"{API}/repos/{REPO}/contents/{path}"
    content = json.dumps(targets, indent=2, ensure_ascii=False) + "\n"
    payload = {
        "message": "feat: update target via Telegram Mini App",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "sha": sha,
        "branch": BRANCH,
    }
    response = requests.put(url, headers=github_headers(token), json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["commit"]["sha"]


def build_target(raw: dict[str, Any]) -> dict[str, Any]:
    site_key = str(raw.get("site_key", "")).strip()
    target_url = str(raw.get("target_url", "")).strip()
    selector = str(raw.get("data_selector", "")).strip()
    extract = str(raw.get("extract_mode", "text")).strip().lower()
    enabled = bool(raw.get("enabled", False))

    if not site_key or len(site_key) > 80 or not all(c.isalnum() or c in "._-" for c in site_key):
        raise ValueError("Invalid site_key")
    if not (target_url.startswith("https://") and len(target_url) <= 2048):
        raise ValueError("target_url must be an HTTPS URL")
    if len(selector) > 500:
        raise ValueError("data_selector is too long")
    if extract not in ALLOWED_EXTRACTS:
        raise ValueError("Unsupported extract_mode")

    return {
        "site_key": site_key,
        "enabled": enabled,
        "target_url": target_url,
        "login": {
            "required": False,
            "username_env": "",
            "password_env": "",
        },
        "task": {
            "data_selector": selector,
            "wait_for_selector": selector,
            "extract": extract,
            "max_items": 50,
        },
    }


def extract_webapp_data(update: dict[str, Any]) -> dict[str, Any] | None:
    message = update.get("message") or {}
    web_app_data = message.get("web_app_data") or {}
    raw = web_app_data.get("data")
    if not isinstance(raw, str) or not raw:
        return None
    payload = json.loads(raw)
    if payload.get("version") != 1 or payload.get("action") != "add_target":
        raise ValueError("Unsupported WebApp payload")
    if not isinstance(payload.get("initData"), str):
        raise ValueError("WebApp initData is missing")
    if not isinstance(payload.get("target"), dict):
        raise ValueError("WebApp target payload is missing")
    return payload


def process_once() -> int:
    bot_token = required("AUTO_ASSISTANT_BOT_TOKEN")
    github_token = required("AutoAssistantWorkerBotAdmin")
    state = load_state()
    offset = state["last_update_id"] + 1

    result = telegram_api("getUpdates", bot_token, json={"offset": offset, "timeout": 0, "allowed_updates": ["message"]})
    updates = result.get("result", [])
    processed = 0

    for update in updates:
        update_id = int(update.get("update_id", 0))
        try:
            payload = extract_webapp_data(update)
            if payload is None:
                save_state(max(state["last_update_id"], update_id))
                state["last_update_id"] = max(state["last_update_id"], update_id)
                continue

            validate_init_data(payload["initData"], bot_token)
            target = build_target(payload["target"])
            targets, sha = github_get_targets(github_token)
            replaced = False
            for index, existing in enumerate(targets):
                if existing.get("site_key") == target["site_key"]:
                    targets[index] = target
                    replaced = True
                    break
            if not replaced:
                targets.append(target)
            commit_sha = github_update_targets(github_token, targets, sha)
            print(f"target update accepted site_key={target['site_key']} replaced={replaced} commit={commit_sha}")
            processed += 1
        except Exception as exc:
            # Never print initData, bot tokens, or GitHub credentials.
            print(f"webapp update {update_id} rejected: {type(exc).__name__}: {exc}")
        finally:
            save_state(max(state["last_update_id"], update_id))
            state["last_update_id"] = max(state["last_update_id"], update_id)

    print(f"Telegram WebApp receiver complete: updates={len(updates)} accepted={processed} at={datetime.now(timezone.utc).isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(process_once())
