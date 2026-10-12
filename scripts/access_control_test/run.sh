#!/usr/bin/env bash
# Codex 2026-10-08: isolated Dataset A access-control generation with live logs.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
export TRANSFORMERS_OFFLINE=1
export HF_HUB_OFFLINE=1
cd "${SCRIPT_DIR}/../.."
python -u "${SCRIPT_DIR}/build_dataset.py" "$@" 2>&1 | tee -a "${SCRIPT_DIR}/build_runs.log"
