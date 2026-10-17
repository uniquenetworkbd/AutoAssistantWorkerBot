# AutoAssistantWorkerBot — Repository Secret Configuration

Keep the following three secrets in **Settings → Secrets and variables → Actions → Repository secrets**. The workflow now reads these exact names directly.

| Repository Secret name | Runtime environment variable | Used for |
|---|---|---|
| `AUTO_ASSISTANT_BOT_TOKEN` | `AUTO_ASSISTANT_BOT_TOKEN` | Telegram Bot API token |
| `AUTO_ASSISTANT_CHAT_ID` | `AUTO_ASSISTANT_CHAT_ID` | Telegram destination chat ID |
| `AUTO_ASSISTANT_GEMINI_API_KEY` | `AUTO_ASSISTANT_GEMINI_API_KEY` | Google Gemini API key |

The names must match exactly. Do not use the legacy names `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, or `GEMINI_API_KEY` unless the workflow is deliberately changed to map from them.

## Runtime validation

The workflow's **Validate secret injection (presence only)** step checks that all three environment variables are non-empty without printing their values. This confirms injection/presence only; it does not prove that the credentials are valid.

- Telegram token and chat ID are tested when the run sends its Telegram report.
- The Gemini key is used for AI selector discovery on login-enabled targets when selectors have not already been learned. The public smoke test does not make a Gemini API request, so it does not validate that key against Google's API.

## Safe live smoke test

1. Open the repository's Actions tab.
2. Select **AutoAssistantWorkerBot**.
3. Click **Run workflow** on branch `main`.
4. Set **Smoke test** to `true`.
5. Start the run and inspect each step.
6. Confirm that a success report arrives in the Telegram chat configured by `AUTO_ASSISTANT_CHAT_ID`.

The smoke test visits only `https://example.com`; it does not log into a real target.

## Target-specific login credentials

For an authorized target that requires login, `input/targets.json` should reference environment variable names instead of containing credentials:

```json
"login": {
  "required": true,
  "username_env": "EXAMPLE_USERNAME",
  "password_env": "EXAMPLE_PASSWORD"
}
```

Target-specific username/password secrets must also be explicitly mapped in the workflow's `env:` block. Never commit secret values to this repository.

## Security rules

- Never write raw tokens, API keys, chat IDs that are confidential, or passwords in source files, logs, or documentation.
- Never print secret values in workflow logs.
- If a credential is exposed, revoke/rotate it with its provider.
