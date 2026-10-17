# AutoAssistantWorkerBot — Secret Configuration

This file is a maintenance reference only. **Never place raw API keys, passwords, bot tokens, or chat credentials in this file or anywhere in Git.**

## Required repository secrets

The production workflow expects these exact GitHub Actions secret names:

| GitHub Secret | Runtime environment variable | Purpose |
|---|---|---|
| `AUTO_ASSISTANT_BOT_TOKEN` | `AUTO_ASSISTANT_BOT_TOKEN` | Telegram Bot API token |
| `AUTO_ASSISTANT_CHAT_ID` | `AUTO_ASSISTANT_CHAT_ID` | Telegram destination chat ID |
| `AUTO_ASSISTANT_GEMINI_API_KEY` | `AUTO_ASSISTANT_GEMINI_API_KEY` | Google Gemini API key |

## Workflow mapping

`.github/workflows/bot_runner.yml` maps the repository secrets directly into the Python process:

```yaml
env:
  AUTO_ASSISTANT_BOT_TOKEN: ${{ secrets.AUTO_ASSISTANT_BOT_TOKEN }}
  AUTO_ASSISTANT_CHAT_ID: ${{ secrets.AUTO_ASSISTANT_CHAT_ID }}
  AUTO_ASSISTANT_GEMINI_API_KEY: ${{ secrets.AUTO_ASSISTANT_GEMINI_API_KEY }}
```

## Target-specific login credentials

For a target that requires authentication, `input/targets.json` should reference environment-variable names rather than storing credentials:

```json
"login": {
  "required": true,
  "username_env": "EXAMPLE_USERNAME",
  "password_env": "EXAMPLE_PASSWORD"
}
```

Those additional secrets must be explicitly mapped into the workflow `env:` block because GitHub Actions does not dynamically expose arbitrary secret names referenced by JSON. Do not put their raw values in `targets.json`.

## Legacy names

The old runtime names `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `GEMINI_API_KEY` are not used by the JSON-first pipeline. The required runtime names are the `AUTO_ASSISTANT_*` names documented above.
