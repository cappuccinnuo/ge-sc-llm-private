#!/usr/bin/env bash
# Train both phases on the authors' published access_control HCG (Google Drive asset),
# mirroring what scripts/run_upstream_graphs.sh / run_hcg_both_phases.sh do for reentrancy:
#   Phase 1  authors' CFG+CG, 114 contracts, 5-fold
#   Phase 2  same graph restricted to its 57 buggy contracts, 10-fold
# The authors' graph ships without token features, so they are encoded here from the
# node 'code' attribute exactly as stored (same choice as the reentrancy author runs).
#
# Usage: run_author_graph.sh [tag]      (default tag: author_graph_v1)
set -euo pipefail
TAG="${1:-author_graph_v1}"

source /home/zhao/miniconda3/etc/profile.d/conda.sh
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm

HERE=scripts/access_control_test
DATA="${HERE}/artifacts/${TAG}"
RUNS="${HERE}/runs/${TAG}"
LABEL=data/upstream_mando_llm/graph_detection/access_control_graph_labels.json
mkdir -p "${DATA}" "${RUNS}/contract" "${RUNS}/line"

if [ ! -f "${DATA}/hcg_author_tok.gpickle" ]; then
  python -B "${HERE}/prepare_author_graph.py" --output "${DATA}/hcg_author.gpickle"
  TRANSFORMERS_OFFLINE=1 python -B scripts/encode_tokenizer_features.py \
    --graph "${DATA}/hcg_author.gpickle" --scheme ids \
    --output "${DATA}/hcg_author_tok.gpickle" 2>&1 | tr '\r' '\n' | grep -E "^nodes|^tokenizer|^scheme|truncated|^wrote"
  python -B scripts/filter_buggy_contracts.py \
    --graph "${DATA}/hcg_author_tok.gpickle" --output "${DATA}/linelevel_author_tok.gpickle"
fi

python -u -B graph_classifier.py \
  --bug_type access_control \
  --compressed_graph "${DATA}/hcg_author_tok.gpickle" \
  --label "${LABEL}" \
  --node_feature inside_token \
  --output_models "${RUNS}/contract/access_control_hgt.pth" \
  --log_dir "${RUNS}/contract/tensorboard" \
  --num_epochs 50 --k_folds 5 --patience 7 --seed 1 \
  --no_progress --verbose_epochs 2>&1 | tee "${RUNS}/contract/train.log"

python -u -B node_classifier.py \
  --bug_type access_control \
  --compressed_graph "${DATA}/linelevel_author_tok.gpickle" \
  --node_feature inside_token \
  --output_models "${RUNS}/line/access_control_hgt.pth" \
  --log_dir "${RUNS}/line/tensorboard" \
  --num_epochs 50 --k_folds 10 --patience 7 --seed 1 --split_by contract \
  --no_progress --verbose_epochs 2>&1 | tee "${RUNS}/line/train.log"
