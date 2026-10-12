#!/usr/bin/env bash
# Find the largest batch size codet5p-770m can encode within this GPU's memory.
# The 4 GiB card is the binding constraint, so probe downward and stop at the
# first size that completes.
set -u

MODEL="${1:-Salesforce/codet5p-770m}"
source /home/zhao/miniconda3/etc/profile.d/conda.sh
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm
export TRANSFORMERS_OFFLINE=1

for B in 16 8 4 2; do
  echo "=========== batch=${B} ==========="
  OUT=$(python scripts/encode_llm_tokens.py \
          --model "${MODEL}" --limit 128 --batch_size "${B}" \
          --output "/tmp/probe770_${B}.gpickle" 2>&1 \
        | tr '\r' '\n')
  if echo "${OUT}" | grep -qiE "out of memory|OutOfMemoryError"; then
    echo "OOM at batch=${B}"
    continue
  fi
  echo "${OUT}" | grep -E "^encoded|embedding dim"
  echo "WORKS at batch=${B}"
  exit 0
done

echo "no batch size succeeded"
exit 1
