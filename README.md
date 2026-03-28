# 404 Link Scanner

Desktop Tkinter app for scanning a site and reporting link results as `Pending`, `200`, `404`, or `ERR`.

## Current Project Structure

```text
.
|-- config.ini
|-- main.py
|-- README.md
|-- requirements.txt
`-- scanner404/
    |-- __init__.py
    |-- config.py
    |-- scanner.py
    `-- ui/
        |-- __init__.py
        |-- app.py
        |-- state.py
        `-- table.py
```

## Module Responsibilities

- `main.py`
  - Entry point for the application.
  - Applies Windows asyncio event-loop policy, then starts the UI.

- `scanner404/config.py`
  - Loads scanner settings from `config.ini` with defaults.
  - Saves updated settings back to `config.ini`.

- `scanner404/scanner.py`
  - Async scanning engine using `aiohttp`.
  - Handles URL queue/workers, status checks (`HEAD` with `GET` fallback), title extraction, and link discovery.
  - Supports pause/stop controls via threading events and emits updates to the UI queue.

- `scanner404/ui/app.py`
  - Main Tkinter app/controller.
  - Handles controls: start, pause/resume, stop, rerun failed links, filter views, CSV export, and copy actions.
  - Polls background scanner updates and keeps counters/table in sync.

- `scanner404/ui/state.py`
  - UI counter defaults and summary formatting.
  - Helper to detect retryable rows (`404` and `ERR`).

- `scanner404/ui/table.py`
  - Table helper utilities (status tags, sortable columns, CSV export of visible rows).

## Configuration

Settings are stored in `config.ini` under `[scanner]`:

- `threads`: number of scanner workers
- `timeout`: request timeout (seconds)
- `crawl_subpages`: `1` to recursively crawl internal links, `0` to only check discovered links
- `user_agent`: HTTP User-Agent header used by requests

These values are loaded at startup and updated when scans are started from the UI.

## Run

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start the app:

```bash
python main.py
```

## Notes

- Results table includes `Status`, `Page Title`, `URL`, and `Source`.
- CSV export writes currently visible rows (respects active filter).
- "Rerun Errors" retries rows currently marked `404` or `ERR`.
