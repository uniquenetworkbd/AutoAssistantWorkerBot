# AutoAssistantWorkerBot

Production-oriented GitHub Actions worker for collecting tabular data from authorized target websites, learning login selectors with Gemini, generating an Excel report, and delivering the report through Telegram.

## Architecture

```text
.github/workflows/bot_runner.yml  -> scheduled/manual GitHub Actions entrypoint
scripts/main.py                   -> orchestration + failure handling
scripts/scraper.py                -> Playwright browsing, login, table extraction
scripts/ai_parser.py              -> Gemini selector discovery
scripts/notifier.py               -> Telegram report/alert delivery
memory/brain.json                 -> learned selectors
memory/error_log.json             -> persistent error history
input/targets.xlsx                -> target configuration
reports/                          -> generated reports (ignored by git)
```

## GitHub configuration

Create these repository secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `GEMINI_API_KEY`

Optional repository variable:

- `GEMINI_MODEL` (defaults to `gemini-2.0-flash`)

If a target needs credentials, store the actual username/password as GitHub Actions secrets or variables and put their names in the `username` and `password` columns of `input/targets.xlsx`. Do not commit real credentials.

## targets.xlsx

Required column: `url`.

Optional columns: `login_required`, `username`, `password`, `table_selector`.

`username` and `password` may contain environment-variable/secret names; the worker resolves those names from the GitHub Actions environment. A literal credential also works technically, but is strongly discouraged.

The first run may call Gemini to discover the login selectors. The resulting selectors are saved under the target URL in `memory/brain.json`. Subsequent runs reuse them.

## Run

- **Manual:** GitHub → Actions → AutoAssistantWorkerBot → Run workflow.
- **Scheduled:** every 30 minutes by default.

The workflow installs Python 3.11, dependencies, and Playwright Chromium. On success it sends `Live_Report_YYYY-MM-DD.xlsx` to Telegram. On failure it logs the error and sends a Telegram alert. Learned selector memory and error logs are committed back to `main` automatically.

## Operational notes

Use this worker only against websites you are authorized to automate and collect data from. Gemini receives sanitized page structure and an optional screenshot for selector discovery; login credentials are not sent to Gemini.

For selector stability, prefer an explicit `table_selector` when the target site has multiple unrelated tables.
