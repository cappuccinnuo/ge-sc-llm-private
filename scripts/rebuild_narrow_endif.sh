#!/usr/bin/env bash
# Rebuild the whole chain with the narrowed end_if span and report the counts that
# the paper's appendix C pins down, so the change can be judged on evidence.
set -eu
source /home/zhao/miniconda3/etc/profile.d/conda.sh
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm
export TREE_SITTER_LIB_DIR=$PWD/build/linux-x86_64
BASE=experiments/ge-sc-data/source_code/reentrancy

echo "=========== 1. regenerate CFGs ==========="
python -m scripts.gen_reentrancy_cfg \
  --source_dir "${BASE}/source_files" \
  --output_dir /tmp/reentrancy_narrow 2>&1 | grep -E "^Found|^Generated"

echo
echo "=========== 2. node/edge totals (paper: 18312 / 19267) ==========="
python scripts/inspect_regen.py /tmp/reentrancy_narrow 2>&1 \
  | grep -E "total nodes|total edges|missing 'node_source"

echo
echo "=========== 3. rebuild labels (paper buggy nodes: 6570) ==========="
python scripts/build_labeled_graph.py \
  --cfg_dir /tmp/reentrancy_narrow \
  --output "${BASE}/hcg_narrow.gpickle" 2>&1 \
  | grep -E "contracts with|buggy nodes"

echo
echo "=========== 4. tokenizer features ==========="
TRANSFORMERS_OFFLINE=1 python scripts/encode_tokenizer_features.py \
  --graph "${BASE}/hcg_narrow.gpickle" \
  --scheme ids \
  --output "${BASE}/tokenizer_ids_narrow.gpickle" 2>&1 \
  | tr '\r' '\n' | grep -E "^wrote node-level"

echo
echo "=========== 5. line-level subgraph ==========="
python scripts/filter_buggy_contracts.py \
  --graph "${BASE}/tokenizer_ids_narrow.gpickle" \
  --output "${BASE}/linelevel_narrow.gpickle" 2>&1 \
  | grep -E "output:|buggy nodes"
