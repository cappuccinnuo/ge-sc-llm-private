#!/usr/bin/env bash
# Pre-download an encoder into the HF cache, retrying around flaky SSL drops.
# huggingface_hub resumes from the .incomplete file, so retries pick up where the
# previous attempt died instead of restarting the transfer.
#
# Usage: fetch_model.sh [model_id] [attempts]
set -u

MODEL="${1:-Salesforce/codet5p-220m}"
ATTEMPTS="${2:-20}"

source /home/zhao/miniconda3/etc/profile.d/conda.sh
conda activate mando
export HF_HUB_DISABLE_TELEMETRY=1

for i in $(seq 1 "${ATTEMPTS}"); do
  echo "=== attempt ${i}/${ATTEMPTS} for ${MODEL} ==="
  python - "$MODEL" <<'PY'
import sys
from transformers import AutoTokenizer, AutoConfig, T5EncoderModel
model_id = sys.argv[1]
AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
AutoConfig.from_pretrained(model_id, trust_remote_code=True)
T5EncoderModel.from_pretrained(model_id, trust_remote_code=True)
print("MODEL READY:", model_id)
PY
  if [ $? -eq 0 ]; then
    echo "DONE: ${MODEL} cached"
    exit 0
  fi
  echo "--- attempt ${i} failed, retrying ---"
  sleep 5
done

echo "GAVE UP after ${ATTEMPTS} attempts"
exit 1
