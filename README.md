# AutoAssistantWorkerBot

JSON-first GitHub Actions automation worker for authorized website automation. The worker uses Playwright for browsing, Gemini for login-selector discovery, JSON for target configuration and learned memory, and Telegram for execution reports and alerts.

## Architecture

```text
.github/
├── SECRETS_CONFIG.md          # exact secret-name mapping; never stores raw secrets
└── workflows/
    └── bot_runner.yml         # manual + 30-minute scheduled execution

input/
└── targets.json               # target URLs, login configuration and task parameters

memory/
├── brain.json                 # learned login selectors and verification metadata
└── error_log.json             # persistent credential-free execution errors

scripts/
├── main.py                    # orchestration and process exit status
├── scraper.py                 # Playwright JSON-first automation engine
├── ai_parser.py               # Gemini selector discovery
└── notifier.py                # Telegram reporting and error persistence

requirements.txt               # Playwright + requests + Gemini only
reports/                       # optional local/generated reports; ignored by Git
```

## Existing GitHub Secrets → runtime mapping

The repository's existing secret names remain unchanged. GitHub Actions maps them to the new runtime environment names:

| Existing GitHub Secret | Runtime environment | Purpose |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | `AUTO_ASSISTANT_BOT_TOKEN` | Telegram Bot API token |
| `TELEGRAM_CHAT_ID` | `AUTO_ASSISTANT_CHAT_ID` | Telegram destination chat ID |
| `GEMINI_API_KEY` | `AUTO_ASSISTANT_GEMINI_API_KEY` | Google Gemini API key |

The detailed maintenance reference is `.github/SECRETS_CONFIG.md`. **Never commit raw secret values.**

Optional repository variable:

- `GEMINI_MODEL` — model name; defaults to `gemini-2.0-flash`.

## Target configuration

`input/targets.json` is a JSON array. A safe disabled starter target is included so the repository can be installed and validated without attempting an unauthorized website.

Example:

```json
[
  {
    "site_key": "example",
    "enabled": true,
    "target_url": "https://authorized.example.com/login",
    "login": {
      "required": true,
      "username_env": "EXAMPLE_USERNAME",
      "password_env": "EXAMPLE_PASSWORD"
    },
    "task": {
      "data_selector": ".result-row",
      "wait_for_selector": ".result-row",
      "extract": "text",
      "max_items": 50
    }
  }
]
```

Supported extraction modes are `text`, `html`, and `links`. If `data_selector` is empty, the worker returns a bounded page-title/body-text record.

### Credentials

Credentials must never be written into `targets.json`. Store them as GitHub Actions secrets and reference their environment-variable names through `username_env` and `password_env`.

GitHub Actions cannot dynamically expose arbitrary secret names referenced by JSON. Therefore, each target-specific credential secret must be explicitly mapped in `.github/workflows/bot_runner.yml`, for example:

```yaml
env:
  EXAMPLE_USERNAME: ${{ secrets.EXAMPLE_USERNAME }}
  EXAMPLE_PASSWORD: ${{ secrets.EXAMPLE_PASSWORD }}
```

## Learned selector memory

`memory/brain.json` starts as `{}`. For a login-enabled target without learned selectors, the worker:

1. Opens the target with Playwright headlessly.
2. Sanitizes the DOM and removes form values and common token/password attributes.
3. Optionally captures the current page screenshot.
4. Sends only sanitized page structure/screenshot to Gemini.
5. Receives `username_selector`, `password_selector`, and `login_button_selector`.
6. Validates all selectors against the live page.
7. Atomically saves the selectors under the target's `site_key`.
8. Reuses and re-verifies the learned selectors on later runs.

Credentials are resolved locally and are never sent to Gemini.

## Error logging

`memory/error_log.json` starts as `[]` and is automatically appended when a target, controller, or Telegram-alert operation fails. Entries contain timestamps, stage, site key/URL when available, error text, and a bounded traceback. Credentials are not intentionally recorded.

## Telegram reports

Every completed run sends a human-readable status message followed by JSON details. Target failures are reported individually. Telegram failures are recorded in `memory/error_log.json` without masking the original automation result.

## GitHub Actions

The workflow:

- uses Python 3.11;
- installs only the dependencies in `requirements.txt`;
- installs Chromium through Playwright;
- runs `python scripts/main.py`;
- maps the existing `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `GEMINI_API_KEY` secrets into the new `AUTO_ASSISTANT_*` runtime variables;
- runs manually through `workflow_dispatch` or every 30 minutes;
- commits `memory/*.json` and `input/targets.json` back to `main` using `stefanzweifel/git-auto-commit-action@v5`.

## First run

The repository currently contains no enabled real target. This is intentional: the automation should not contact a site until an authorized target is configured. After adding an authorized target and any required credential secret mappings, use **GitHub → Actions → AutoAssistantWorkerBot → Run workflow**.

## Dependencies

`requirements.txt` intentionally contains only:

```text
playwright
requests
google-generativeai
```

(The actual file uses pinned-compatible version ranges.) There is no pandas, openpyxl, lxml, Excel input, or Excel report generation in the JSON-first pipeline.

## Security and authorization

Use this worker only for websites and accounts you are authorized to automate. Do not bypass authentication, CAPTCHA, access controls, rate limits, or other security controls. Keep secrets in GitHub Actions Secrets and rotate them through GitHub/provider controls when necessary.

## Operational limitations

- GitHub Actions secrets cannot be dynamically injected from names stored only in `targets.json`; target-specific secrets require explicit workflow mappings.
- A real end-to-end production run requires valid repository secrets and at least one authorized enabled target.
- The connected repository tooling can verify repository files and workflow configuration, but a live Actions run is only verifiable when a workflow-dispatch/run capability is available and the run can be inspected.
