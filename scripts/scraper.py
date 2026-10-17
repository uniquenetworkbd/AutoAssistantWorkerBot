"""Playwright JSON-first scraping and selector-learning engine."""
from __future__ import annotations

import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from ai_parser import detect_login_selectors

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "input" / "targets.json"
BRAIN = ROOT / "memory" / "brain.json"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid JSON file: {path}: {exc}") from exc


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _load_targets() -> list[dict[str, Any]]:
    data = _read_json(TARGETS, [])
    if not isinstance(data, list):
        raise ValueError("input/targets.json must contain a JSON array")
    targets: list[dict[str, Any]] = []
    for index, target in enumerate(data):
        if not isinstance(target, dict):
            raise ValueError(f"Target #{index + 1} must be a JSON object")
        if not target.get("site_key") or not target.get("target_url"):
            raise ValueError(f"Target #{index + 1} requires site_key and target_url")
        targets.append(target)
    return targets


def _load_brain() -> dict[str, Any]:
    data = _read_json(BRAIN, {})
    if not isinstance(data, dict):
        raise ValueError("memory/brain.json must contain a JSON object")
    return data


def _selectors_for(brain: dict[str, Any], site_key: str) -> dict[str, str] | None:
    entry = brain.get(site_key)
    if not isinstance(entry, dict):
        return None
    selectors = entry.get("login_selectors", {})
    if not isinstance(selectors, dict):
        return None
    keys = ("username_selector", "password_selector", "login_button_selector")
    if not all(isinstance(selectors.get(key), str) and selectors[key].strip() for key in keys):
        return None
    return {key: selectors[key].strip() for key in keys}


def _validate_selectors(page, selectors: dict[str, str]) -> None:
    for key, selector in selectors.items():
        if page.locator(selector).count() == 0:
            raise ValueError(f"Selector does not match page: {key}={selector}")


def _credentials(login: dict[str, Any]) -> tuple[str, str]:
    username_env = str(login.get("username_env", "")).strip()
    password_env = str(login.get("password_env", "")).strip()
    if not username_env or not password_env:
        raise ValueError("Login requires username_env and password_env")
    username = os.getenv(username_env, "")
    password = os.getenv(password_env, "")
    if not username or not password:
        raise ValueError(f"Configured login secrets are missing: {username_env}/{password_env}")
    return username, password


def _login(page, login: dict[str, Any], selectors: dict[str, str]) -> None:
    username, password = _credentials(login)
    page.locator(selectors["username_selector"]).first.fill(username)
    page.locator(selectors["password_selector"]).first.fill(password)
    page.locator(selectors["login_button_selector"]).first.click()
    page.wait_for_load_state("domcontentloaded", timeout=30_000)
    page.wait_for_timeout(1_000)


def _extract(page, task: dict[str, Any], url: str) -> list[dict[str, Any]]:
    selector = str(task.get("data_selector", "")).strip()
    wait_selector = str(task.get("wait_for_selector", "")).strip()
    extract_mode = str(task.get("extract", "text")).strip().lower()
    max_items = max(1, min(int(task.get("max_items", 50)), 500))

    if wait_selector:
        page.locator(wait_selector).first.wait_for(state="visible", timeout=30_000)
    if not selector:
        return [{"source_url": url, "title": page.title(), "text": page.locator("body").inner_text()[:20_000]}]

    locators = page.locator(selector)
    count = min(locators.count(), max_items)
    records: list[dict[str, Any]] = []
    for index in range(count):
        item = locators.nth(index)
        if extract_mode == "html":
            value: Any = item.inner_html()
        elif extract_mode == "links":
            value = item.get_attribute("href") or item.inner_text()
        else:
            value = item.inner_text()
        records.append({"source_url": url, "index": index + 1, "value": value})
    if not records:
        raise ValueError(f"data_selector matched no elements: {selector}")
    return records


def run(*, smoke_test: bool = False) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    configured_targets = _load_targets()
    if smoke_test:
        # Safe public smoke target used only for a manual workflow validation.
        targets = [{
            "site_key": "github_actions_smoke_test",
            "enabled": True,
            "target_url": "https://example.com",
            "login": {"required": False},
            "task": {"data_selector": "h1", "extract": "text", "max_items": 1},
        }]
    else:
        targets = [target for target in configured_targets if target.get("enabled", True)]

    brain = _load_brain()
    results: list[dict[str, Any]] = []

    if not targets:
        return {
            "run_id": started.strftime("%Y%m%dT%H%M%SZ"),
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "success",
            "message": "No enabled targets configured",
            "targets": [],
        }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        try:
            for target in targets:
                site_key = str(target["site_key"]).strip()
                url = str(target["target_url"]).strip()
                login = target.get("login", {})
                task = target.get("task", {})
                page = context.new_page()
                result: dict[str, Any] = {
                    "site_key": site_key,
                    "url": url,
                    "status": "failed",
                    "learned_selectors": False,
                    "records": [],
                    "error": None,
                }
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                    if bool(login.get("required", False)):
                        selectors = _selectors_for(brain, site_key)
                        if selectors is None:
                            screenshot = page.screenshot(full_page=False)
                            selectors = detect_login_selectors(page.content(), screenshot)
                            _validate_selectors(page, selectors)
                            brain[site_key] = {
                                "target_url": url,
                                "login_selectors": selectors,
                                "learned_at": datetime.now(timezone.utc).isoformat(),
                                "success_count": 0,
                            }
                            _atomic_write_json(BRAIN, brain)
                            result["learned_selectors"] = True
                        _login(page, login, selectors)
                        result["authenticated"] = True
                    result["records"] = _extract(page, task, url)
                    result["status"] = "success"
                    if site_key in brain and isinstance(brain[site_key], dict):
                        brain[site_key]["last_verified_at"] = datetime.now(timezone.utc).isoformat()
                        brain[site_key]["success_count"] = int(brain[site_key].get("success_count", 0)) + 1
                        _atomic_write_json(BRAIN, brain)
                except PlaywrightTimeoutError as exc:
                    result["error"] = f"Playwright timeout: {exc}"
                except Exception as exc:
                    result["error"] = str(exc)
                    result["traceback"] = traceback.format_exc(limit=6)
                finally:
                    page.close()
                results.append(result)
        finally:
            context.close()
            browser.close()

    statuses = [item["status"] for item in results]
    if statuses and all(status == "success" for status in statuses):
        status = "success"
    elif any(status == "success" for status in statuses):
        status = "partial"
    else:
        status = "failed"

    return {
        "run_id": started.strftime("%Y%m%dT%H%M%SZ"),
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "target_count": len(results),
        "success_count": sum(item["status"] == "success" for item in results),
        "failure_count": sum(item["status"] != "success" for item in results),
        "smoke_test": smoke_test,
        "targets": results,
    }
