#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=1
export TRANSFORMERS_OFFLINE=1
export HF_HUB_OFFLINE=1
cd "${SCRIPT_DIR}/../.."
python -u "${SCRIPT_DIR}/run_suite.py" "$@"
