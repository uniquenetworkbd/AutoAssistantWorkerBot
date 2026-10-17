# AutoAssistantWorkerBot

JSON-first GitHub Actions automation worker for websites and accounts the operator is authorized to automate. It uses Playwright for browser execution, Gemini for login-selector discovery, JSON for target configuration and learned memory, and Telegram for run reports.

## Repository layout

```text
.github/
├── SECRETS_CONFIG.md
└── workflows/
    └── bot_runner.yml
input/
└── targets.json
memory/
├── brain.json
└── error_log.json
scripts/
├── main.py
├── scraper.py
├── ai_parser.py
└── notifier.py
requirements.txt
```

## Required GitHub Repository Secrets

Create these exact names under **Settings → Secrets and variables → Actions → Repository secrets**:

| Secret name | Purpose |
|---|---|
| `AUTO_ASSISTANT_BOT_TOKEN` | Telegram Bot API token |
| `AUTO_ASSISTANT_CHAT_ID` | Telegram destination chat ID |
| `AUTO_ASSISTANT_GEMINI_API_KEY` | Google Gemini API key |

The workflow maps each secret directly to the runtime environment variable of the same name. It also checks that all three values are injected without printing them. This check confirms non-empty values only, not credential validity. Never commit secret values.

Optional repository variable:
- `GEMINI_MODEL` — Gemini model name; the code defaults to `gemini-2.0-flash`.

See [Secret Configuration](.github/SECRETS_CONFIG.md) for validation details.

## Target configuration

`input/targets.json` is a JSON array. The repository starts with a disabled public `https://example.com` target so scheduled runs do not contact an unintended website.

Example for an authorized target:

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

Supported extraction modes are `text`, `html`, and `links`. If `data_selector` is empty, the worker returns a bounded page-title/body-text record. Login credentials belong in GitHub Actions Secrets and must be mapped explicitly into the workflow environment.

## Safe live smoke test

The manual workflow provides a **Smoke test** input. Set it to `true` to validate the GitHub Actions execution path against the public `https://example.com` page. It does not log in to a real target and does not call Gemini for selector discovery.

The run checks:
1. Python 3.11 setup and dependency installation.
2. Presence of the three required repository secrets (values are never printed).
3. Playwright Chromium installation.
4. JSON-first controller and browser execution.
5. Telegram report delivery.
6. Commit/push behavior for generated JSON state, when there are changes.

To run it:
1. Open the repository's **Actions** tab.
2. Select **AutoAssistantWorkerBot**.
3. Click **Run workflow** and keep branch `main`.
4. Set **Smoke test** to `true`.
5. Start the run, then inspect the job logs and Telegram report.

The smoke test checks that the Gemini secret is present, but does **not** validate that the Gemini key is accepted by Google's API. Gemini is called when an enabled login target needs AI selector discovery.

## Learned selector memory

`memory/brain.json` stores learned selectors by `site_key`. For a login-enabled target without saved selectors, the worker sanitizes page DOM metadata, optionally captures a screenshot, asks Gemini for CSS selectors, validates them against the page, saves them, and reuses them on later runs. Credentials are resolved locally and are not intentionally sent to Gemini.

## Error logging and reports

`memory/error_log.json` stores bounded execution errors. The notifier sends a human-readable Telegram summary followed by JSON details; target failures and controller errors also produce alerts. Never include raw credentials in target configuration or custom error messages.

## Workflow behavior

- Python 3.11.
- Dependencies from `requirements.txt`: Playwright, Requests, and the current Google GenAI SDK.
- Manual `workflow_dispatch` with a safe smoke-test switch.
- Scheduled execution every 30 minutes.
- Direct secret-name mapping using the three `AUTO_ASSISTANT_*` names.
- A serialized workflow group to reduce concurrent writes.
- A retrying Git push that fetches and rebases onto the latest `main` after a non-fast-forward rejection.
- Only `memory/*.json` and `input/targets.json` are staged by the generated-state commit step.

## Safety and authorization

Use this worker only on websites/accounts you are authorized to automate. Do not bypass authentication challenges, CAPTCHAs, access controls, rate limits, or other security measures.

## Verification status

The workflow and documentation are committed to `main`. A successful live run must still be confirmed from the Actions run and Telegram report; a code commit alone is not proof of successful execution.
