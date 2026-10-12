#!/usr/bin/env bash
# Contract-level (Phase 1) training under the paper's settings:
#   5-fold cross validation, full corpus at Clean : Buggy = 1 : 1, patience 7.
#
# Usage: train_contractlevel.sh <graph.gpickle> <node_feature> <tag>
set -eu

REPO=/home/zhao/SmartContract/ge-sc-llm
GRAPH="$1"
FEATURE="$2"
TAG="$3"
BASE="${REPO}/experiments/ge-sc-data/source_code/reentrancy"
# Forward anything past the three positional arguments, so extra flags reach
# graph_classifier.py instead of being silently dropped.
if [ "$#" -gt 3 ]; then shift 3; else shift "$#"; fi

source /home/zhao/miniconda3/etc/profile.d/conda.sh
conda activate mando
cd "${REPO}"

python -u graph_classifier.py \
  --compressed_graph "${GRAPH}" \
  --label "${BASE}/graph_labels.json" \
  --dataset "${BASE}/source_files" \
  --testset "${BASE}/source_files" \
  --node_feature "${FEATURE}" \
  --output_models "${REPO}/models/contractlevel/${TAG}/reentrancy_hgt.pth" \
  --log_dir "${REPO}/logs/contractlevel_${TAG}" \
  --num_epochs 50 \
  --k_folds 5 \
  --patience 7 \
  --seed 1 \
  --no_progress \
  "$@"
