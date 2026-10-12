#!/usr/bin/env bash
# Generate the remaining tokenizer feature variants for ablation.
set -eu
source /home/zhao/miniconda3/etc/profile.d/conda.sh
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm
export TRANSFORMERS_OFFLINE=1

for S in ids_norm hashed_bow; do
  echo "=========== scheme=${S} ==========="
  python scripts/encode_tokenizer_features.py --scheme "${S}" 2>&1 \
    | tr '\r' '\n' | grep -E "^token lengths|^nodes truncated|^wrote node-level"
done
