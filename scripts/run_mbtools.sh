
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}/.."
source "${ROOT_DIR}/.venv/bin/activate" 2>/dev/null || true
export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"
python -m mbtools   "${1:-.}"   --ua "PierreTools/1.0 (pierre@example.com)"   --search-fallback   --cache
