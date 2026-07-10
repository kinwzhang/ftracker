#!/usr/bin/env python3
"""Trigger script for the ftracker Django app.

Bootstraps the project (ensures the SQLite database exists and migrations
are applied) and then launches the Django development server.

Usage (from the project root):

    python trigger.py            # default: 127.0.0.1:8000
    python trigger.py 0.0.0.0:9000

Equivalent to running `tracker/setup.py` followed by `manage.py runserver`.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def bootstrap() -> None:
    """Ensure the database exists and migrations are applied."""
    from tracker.setup import main as setup_main  # noqa: E402

    rc = setup_main()
    if rc != 0:
        raise SystemExit(rc)


def runserver(address: str) -> None:
    """Launch Django's development server on ``address``."""
    from django.core.management import execute_from_command_line  # noqa: E402

    execute_from_command_line(["manage.py", "runserver", address])


def main() -> int:
    address = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:8000"

    # Django's StatReloader re-execs ``sys.argv`` on startup so the child can
    # actually run the dev server with autoreload enabled. That second exec
    # would otherwise print the entire bootstrap banner again and re-run the
    # bootstrap (harmless but noisy). Detect the re-exec and skip both.
    # The env var Django sets is ``RUN_MAIN=true`` (see
    # ``django.utils.autoreload.DJANGO_AUTORELOAD_ENV``).
    is_autoreload_re_exec = os.environ.get("RUN_MAIN") == "true"

    if not is_autoreload_re_exec:
        print(f"== ftracker trigger — booting at http://{address}/ ==")
        bootstrap()

        print("")
        print(f"Starting development server at http://{address}/")
        print("Quit the server with CTRL-C.")
        print("")
    else:
        print(f"== ftracker trigger — reloading at http://{address}/ ==")

    os.chdir(PROJECT_ROOT)
    runserver(address)
    return 0


if __name__ == "__main__":
    sys.exit(main())