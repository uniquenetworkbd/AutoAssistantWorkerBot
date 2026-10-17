"""Playwright worker: target loading, selector learning, login and table extraction."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from ai_parser import detect_login_selectors

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "input" / "targets.xlsx"
BRAIN = ROOT / "memory" / "brain.json"
REPORT_DIR = ROOT / "reports"


def _load_brain() -> dict[str, Any]:
    if not BRAIN.exists():
        return {}
    try:
        value = json.loads(BRAIN.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _save_brain(brain: dict[str, Any]) -> None:
    BRAIN.write_text(json.dumps(brain, indent=2, ensure_ascii=False), encoding="utf-8")


def _targets() -> pd.DataFrame:
    if not TARGETS.exists():
        raise FileNotFoundError(f"Missing {TARGETS}. Copy the documented template into input/targets.xlsx")
    df = pd.read_excel(TARGETS, engine="openpyxl")
    required = {"url"}
    missing = required - set(df.columns.str.lower())
    if missing:
        raise ValueError(f"targets.xlsx missing required columns: {sorted(missing)}")
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df.dropna(subset=["url"])


def _env_secret(row: pd.Series, column: str) -> str:
    value = str(row.get(column, "")).strip()
    if not value or value.lower() == "nan":
        return ""
    return os.getenv(value, value)


def _selector_from_brain(brain: dict[str, Any], url: str) -> dict[str, str] | None:
    entry = brain.get(url)
    return entry if isinstance(entry, dict) and all(entry.get(k) for k in ("username_selector", "password_selector", "login_button_selector")) else None


def _login(page, row: pd.Series, selectors: dict[str, str], url: str) -> None:
    username = _env_secret(row, "username")
    password = _env_secret(row, "password")
    if not username or not password:
        raise ValueError(f"Login is required for {url}, but username/password are not configured")
    page.locator(selectors["username_selector"]).fill(username)
    page.locator(selectors["password_selector"]).fill(password)
    page.locator(selectors["login_button_selector"]).click()
    page.wait_for_load_state("domcontentloaded", timeout=30_000)
    page.wait_for_timeout(1_500)


def run() -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    brain = _load_brain()
    frames: list[pd.DataFrame] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        try:
            for _, row in _targets().iterrows():
                url = str(row["url"]).strip()
                page = context.new_page()
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                    selectors = _selector_from_brain(brain, url)
                    login_required = str(row.get("login_required", "yes")).strip().lower() not in {"no", "false", "0"}
                    if login_required:
                        if not selectors:
                            html = page.content()
                            screenshot = page.screenshot(full_page=False)
                            selectors = detect_login_selectors(html, screenshot)
                            # Validate AI output before persisting it.
                            for key, selector in selectors.items():
                                if page.locator(selector).count() == 0:
                                    raise ValueError(f"AI selector did not match page: {key}={selector}")
                            brain[url] = selectors
                            _save_brain(brain)
                        _login(page, row, selectors, url)

                    table_selector = str(row.get("table_selector", "")).strip()
                    if table_selector and table_selector.lower() != "nan":
                        html = page.locator(table_selector).first.inner_html()
                        table_html = f"<table>{html}</table>"
                    else:
                        table_html = page.content()
                    tables = pd.read_html(table_html)
                    if not tables:
                        raise ValueError(f"No HTML table found at {url}")
                    for index, frame in enumerate(tables):
                        out = frame.copy()
                        out.insert(0, "source_url", url)
                        out.insert(1, "source_table", index + 1)
                        frames.append(out)
                except PlaywrightTimeoutError as exc:
                    raise RuntimeError(f"Timeout while processing {url}") from exc
                finally:
                    page.close()
        finally:
            context.close()
            browser.close()

    if not frames:
        raise RuntimeError("No data was extracted from any target")
    report = pd.concat(frames, ignore_index=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = REPORT_DIR / f"Live_Report_{stamp}.xlsx"
    report.to_excel(path, index=False, engine="openpyxl")
    return path
