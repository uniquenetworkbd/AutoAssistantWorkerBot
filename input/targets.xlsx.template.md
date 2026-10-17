# targets.xlsx template

The repository contains `input/targets.xlsx` as a starter workbook. Columns:

- `url` — required target URL.
- `login_required` — `yes`/`no` (defaults to login required when omitted).
- `username` — either a literal value (not recommended) or the name of a GitHub Actions environment variable/secret.
- `password` — either a literal value (not recommended) or the name of a GitHub Actions environment variable/secret.
- `table_selector` — optional CSS selector for the table/container to extract; blank means all HTML tables on the page.

For production, keep credentials out of the workbook. Put the values in GitHub Actions secrets/variables and put only the variable/secret names in the workbook.

Example:

| url | login_required | username | password | table_selector |
|---|---|---|---|---|
| https://example.com/login | yes | TARGET_USERNAME_ENV | TARGET_PASSWORD_ENV | |
