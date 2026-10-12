#!/usr/bin/env bash
# Label the two locally built fused graphs in both modes and compare with the author graphs.
# Usage: bash Test_code/labeling_v3/run_local.sh [version]     (default v1)
set -euo pipefail
VERSION="${1:-v1}"
PY=/home/zhao/miniconda3/envs/mando/bin/python
cd /home/zhao/SmartContract/ge-sc-llm
OUT="Test_code/labeling_v3/artifacts/${VERSION}"

RE=experiments/ge-sc-data/source_code/reentrancy
AC=scripts/access_control_test/artifacts/dataset_a_source_range_v1
for MODE in clean author; do
  "$PY" -B Test_code/labeling_v3/label_local_graph.py --bug_type reentrancy \
    --graph "$RE/tokenizer_ids_narrow.gpickle" --contract_labels "$RE/graph_labels.json" \
    --mode "$MODE" --output "$OUT/reentrancy/hcg_tok_${MODE}.gpickle" --compare
  "$PY" -B Test_code/labeling_v3/label_local_graph.py --bug_type access_control \
    --graph "$AC/tokenizer_ids_codet5p-770m_hcg_compressed_graphs.gpickle" --contract_labels "$AC/graph_labels.json" \
    --mode "$MODE" --output "$OUT/access_control/hcg_tok_${MODE}.gpickle" --compare
done
