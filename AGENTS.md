# KerryMonitoring repository guide

## Purpose

This is a small Python service that monitors prices for Kerry automotive
chemical products and their competitors:

1. Read Excel attachments from an unread Yandex mailbox.
2. Parse Kerry and competitor article mappings.
3. Query the Autopiter SOAP API for minimum prices.
4. Generate an Excel report with Autopiter product links.
5. Send the report through Yandex SMTP.

Production is expected to run from `/opt/KerryMonitoring` under
`kerrymonitoring.service`.

This repository workspace is for development and local verification only.
The real application executes on the production server, not on the local
development machine. Local test results do not prove that server credentials,
network access, filesystem state, systemd configuration, or external services
are working; production deployment and integration checks must be performed
on the server.

## Main workflow

`main.py` is the application entry point. `check_prices()`:

- downloads and merges all new `.xls`/`.xlsx` attachments;
- falls back to the local spreadsheet or `config.ARTICLES`;
- resumes interrupted API work from `progress_state.json`;
- waits 24 hours after an Autopiter HTTP 500 rate-limit response;
- builds and emails the report;
- saves `prices.json` and creates `articles_done.flag`.

After the initial run, `main.py` schedules `check_prices()` hourly.

Data flow:

```text
email_receiver.py -> import_articles.py -> main.py
                                            |
                                            v
                                      autopiter.py
                                            |
                                            v
                         excel_report.py -> notifier.py
```

## Important files

- `autopiter.py`: SOAP authorization, catalog lookup, offer lookup, retries,
  volume filtering, and `RateLimitError`.
- `email_receiver.py`: Yandex IMAP polling and Excel attachment extraction.
- `import_articles.py`: `.xls`/`.xlsx` parsing and optional `config.py`
  `ARTICLES` replacement.
- `excel_report.py`: creates the `Цены` and `Отсортированные` worksheets.
- `notifier.py`: sends the generated workbook through Yandex SMTP SSL.
- `config.example.py`: required configuration shape.
- `kerrymonitoring.service`: production systemd unit.
- `test_*.py`, `check_api.py`, `debug_*.py`, `send_partial.py`: manual
  integration/debug scripts, not a conventional automated test suite.

## Configuration and runtime state

Copy `config.example.py` to ignored `config.py` and set:

- `AUTOPITER_USER_ID`
- `AUTOPITER_PASSWORD`
- `EMAIL_FROM`
- `EMAIL_PASSWORD`
- `EMAIL_TO`

Never commit credentials or generated customer data.

Runtime files are relative to the process working directory:

- `articles_received.xls` or `.xlsx`: most recently downloaded attachment.
- `progress_state.json`: resumable processing checkpoint.
- `prices.json`: last successfully fetched prices.
- `articles_done.flag`: prevents reprocessing without new mail.

These files affect control flow. Do not delete or change them casually when
diagnosing a production run.

## Input contract

The first spreadsheet row is a header. Only white/unfilled data rows are
processed; highlighted rows (including yellow rows) are ignored. Columns are:

1. manager — ignored
2. competitor brand
3. competitor article
4. competitor product name
5. unused/garbage — ignored
6. Kerry article
7. Kerry product name

Articles are normalized by replacing common Cyrillic lookalikes with Latin
characters. Multiple rows for one Kerry article are merged into its
competitor mapping. Rows missing either article, or mapping an article to
itself, are skipped.

Imported competitor mappings store both brand and source product name. The
report groups competitors into brand columns and includes the source product
name in competitor cells. Legacy `config.ARTICLES` mappings whose values are
plain brand strings remain supported.

## Development commands

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python main.py
python import_articles.py articles.xls --dry-run
python check_api.py
python debug_missing_prices.py
python debug_api_dump.py
python send_partial.py
```

Every logic change must add or update an automated test that covers the
changed behavior. Run the relevant automated tests locally before considering
the work complete. Also run targeted manual scripts when useful.

External API, IMAP, and SMTP checks require real credentials and network
access. Do not treat local unit tests as replacements for server-side
integration verification, and do not run production integrations locally
unless the task explicitly calls for it.

## Engineering constraints

- Preserve the flat-file checkpoint/resume behavior when changing the main
  loop.
- Keep support for both legacy `.xls` (`xlrd`) and `.xlsx` (`openpyxl`).
- Preserve article normalization and optional volume matching.
- Treat Autopiter HTTP 500 as rate limiting unless the API contract is
  deliberately changed.
- Keep report column ordering deterministic: fixed columns first, then
  competitor brands in first-seen order.
- User-facing logs and report labels are currently Russian.
- The Autopiter endpoint is legacy plain HTTP. Do not silently change its
  protocol or SOAP contract without verifying service compatibility.

## Production operations

```bash
sudo systemctl start kerrymonitoring
sudo systemctl status kerrymonitoring
sudo journalctl -u kerrymonitoring -f
```

The service uses `/opt/KerryMonitoring/.venv/bin/python`, restarts on failure,
and writes logs to the systemd journal.
