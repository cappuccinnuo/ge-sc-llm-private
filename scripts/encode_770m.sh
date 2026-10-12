#!/usr/bin/env bash
# Full-corpus encoding with the model the paper reports, codet5p-770m (1024-dim).
# batch=16 was probed to fit this 4 GiB card, so no downshift is needed.
set -eu

source /home/zhao/miniconda3/etc/profile.d/conda.sh
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm
export TRANSFORMERS_OFFLINE=1

python scripts/encode_llm_tokens.py \
  --model Salesforce/codet5p-770m \
  --batch_size 16 \
  --graph_type cfg \
  --coarse_output experiments/ge-sc-data/source_code/reentrancy/cfg/encode_coarse_grained_token_codet5p-770m.pt
