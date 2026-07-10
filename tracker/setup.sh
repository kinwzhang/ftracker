#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
find_project_root() {
    local dir="$SCRIPT_DIR"
    while [ "$dir" != "/" ]; do
        if [ -f "$dir/manage.py" ]; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    echo "$SCRIPT_DIR"
    return 1
}

PROJECT_DIR="$(find_project_root)"
DB_DIR="$SCRIPT_DIR"
DB_PATH="$DB_DIR/db.sqlite3"

cd "$PROJECT_DIR"

if [ ! -f "$DB_PATH" ]; then
    echo "Database not found at $DB_PATH"
    echo "Running migrations to create it..."
    python3 manage.py migrate --run-syncdb
    if [ -f "$PROJECT_DIR/db.sqlite3" ]; then
        mv "$PROJECT_DIR/db.sqlite3" "$DB_PATH"
        echo "Moved database to $DB_PATH"
    fi
    echo "Database created."
else
    echo "Database already exists at $DB_PATH"
fi

echo "Applying any pending migrations..."
python3 manage.py migrate
echo ""
echo "Setup complete. Database at: $DB_PATH"
