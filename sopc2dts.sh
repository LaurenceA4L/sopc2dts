#!/usr/bin/env sh
# sopc2dts — thin shell wrapper for the Python port.
#
# Usage: ./sopc2dts.sh [options]   (same flags as the original Java tool)
#
# Prefers a local .venv if present; falls back to the system Python 3.
# Requires Python 3.10 or later.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- pick an interpreter ---------------------------------------------------

if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON="python"
else
    echo "sopc2dts: Python 3.10+ is required but was not found on PATH." >&2
    exit 1
fi

# --- version check ---------------------------------------------------------

PY_VER=$("$PYTHON" -c "import sys; print('%d%02d' % sys.version_info[:2])")
if [ "$PY_VER" -lt 310 ] 2>/dev/null; then
    echo "sopc2dts: Python 3.10+ required (found $("$PYTHON" --version 2>&1))." >&2
    exit 1
fi

# --- run -------------------------------------------------------------------

exec "$PYTHON" -m sopc2dts_py "$@"
