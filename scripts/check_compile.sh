
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}/.."
export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"
python -m py_compile ${ROOT_DIR}/src/mbtools/*.py
