#!/usr/bin/env bash
# Produce the buggy-contracts-only graphs the line-level phase should train on,
# for every node-feature variant that exists.
set -eu
source /home/zhao/miniconda3/etc/profile.d/conda.sh
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm

BASE=experiments/ge-sc-data/source_code/reentrancy

run () {
  local src="$1"; local dst="$2"
  if [ -f "${src}" ]; then
    echo "=========== ${dst} ==========="
    python scripts/filter_buggy_contracts.py --graph "${src}" --output "${dst}"
    echo
  else
    echo "skip (missing): ${src}"
  fi
}

# structure only
run "${BASE}/hcg_compressed_graphs.gpickle" "${BASE}/linelevel_hcg.gpickle"

# tokenizer features (the paper's node feature extractor)
for S in ids ids_norm hashed_bow; do
  run "${BASE}/tokenizer_${S}_codet5p-770m_hcg_compressed_graphs.gpickle" \
      "${BASE}/linelevel_tokenizer_${S}.gpickle"
done
