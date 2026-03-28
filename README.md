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

## Build (Nuitka)

Use the provided build script:

```powershell
.\build.bat
```

Default behavior:

- Builds in `standalone` mode
- Produces folder output under `build/main.dist`
- Builds an Inno Setup installer EXE under `build/installer`

Prerequisite for installer build:

- Install Inno Setup 6 (`ISCC.exe`)
- `build.bat` will auto-try install using `winget` or `choco` when `ISCC.exe` is missing

Optional: disable automatic Inno Setup install attempt:

```powershell
$env:AUTO_INSTALL_INNO="0"; .\build.bat
```

Optional: skip installer generation in standalone mode:

```powershell
$env:BUILD_INSTALLER="0"; .\build.bat
```

Optional onefile mode:

```powershell
$env:BUILD_MODE="onefile"; .\build.bat
```

## Notes

- Results table includes `Status`, `Page Title`, `URL`, and `Source`.
- CSV export writes currently visible rows (respects active filter).
- "Rerun Errors" retries rows currently marked `404` or `ERR`.

## GitHub Actions (Manual Build and Publish)

This repo includes a manual workflow at `.github/workflows/manual-build-publish.yml`.

How to use it:

1. Push your code to GitHub.
2. Open **Actions** and select **Manual Build and Publish**.
3. Click **Run workflow**.
4. Enter:
  - `version`: release version like `1.0.0`
  - `publish`: `false` for build only, `true` to publish a release

Behavior:

- If `publish=false`, the workflow builds `scanner404-setup.exe` and uploads it as an artifact.
- If `publish=true`, it builds first, then creates a GitHub Release and uploads the installer executable.

Optional approval gate:

- The publish job uses the `release` environment.
- In your GitHub repo settings, configure the `release` environment with required reviewers to enforce manual approval before publishing.
