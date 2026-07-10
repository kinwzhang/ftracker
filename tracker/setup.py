#!/usr/bin/env python3
"""Initialize the project database.

Locates the Django project root (by walking up the directory tree until
``manage.py`` is found) and ensures ``db.sqlite3`` exists in this script's
directory. If the database is missing, runs ``manage.py migrate --run-syncdb``
to create it from scratch and moves the freshly-created file from the project
root into this directory. Then applies any pending migrations.

Equivalent of ``setup.sh``.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def find_project_root(start: Path) -> Path | None:
    """Walk up from ``start`` until a directory containing ``manage.py`` is found."""
    dir_path = start
    while dir_path != dir_path.parent:
        if (dir_path / "manage.py").is_file():
            return dir_path
        dir_path = dir_path.parent
    return None


def run_manage(project_dir: Path, *args: str) -> None:
    """Invoke ``manage.py`` with the given arguments using the current Python."""
    cmd = [sys.executable, str(project_dir / "manage.py"), *args]
    subprocess.run(cmd, cwd=project_dir, check=True)


def main() -> int:
    project_dir = find_project_root(SCRIPT_DIR)
    if project_dir is None:
        print(f"Could not locate manage.py starting from {SCRIPT_DIR}", file=sys.stderr)
        return 1

    db_path = SCRIPT_DIR / "db.sqlite3"

    if not db_path.is_file():
        print(f"Database not found at {db_path}")
        print("Running migrations to create it...")
        run_manage(project_dir, "migrate", "--run-syncdb")
        created_at_root = project_dir / "db.sqlite3"
        if created_at_root.is_file():
            shutil.move(str(created_at_root), str(db_path))
            print(f"Moved database to {db_path}")
        print("Database created.")
    else:
        print(f"Database already exists at {db_path}")

    print("Applying any pending migrations...")
    run_manage(project_dir, "migrate")

    print("")
    print(f"Setup complete. Database at: {db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())