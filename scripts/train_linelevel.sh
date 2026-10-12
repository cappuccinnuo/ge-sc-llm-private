#!/usr/bin/env bash
# Line-level (Phase 2) training under the paper's settings:
#   10-fold cross validation, buggy contracts only, patience 7.
#
# Usage: train_linelevel.sh <graph.gpickle> <node_feature> <tag>
set -eu

REPO=/home/zhao/SmartContract/ge-sc-llm
GRAPH="$1"
FEATURE="$2"
TAG="$3"
# Anything after the three positional arguments is forwarded to node_classifier.py.
# Without this a flag such as --split_by snippet is silently dropped and the run
# quietly falls back to the default, which is exactly what the "Split mode:" line
# printed at the end of training is there to catch.
if [ "$#" -gt 3 ]; then shift 3; else shift "$#"; fi

source /home/zhao/miniconda3/etc/profile.d/conda.sh
conda activate mando
cd "${REPO}"

python -u node_classifier.py \
  --compressed_graph "${GRAPH}" \
  --dataset "${REPO}/experiments/ge-sc-data/source_code/reentrancy/source_files" \
  --testset "${REPO}/experiments/ge-sc-data/source_code/reentrancy/source_files" \
  --node_feature "${FEATURE}" \
  --output_models "${REPO}/models/linelevel/${TAG}/reentrancy_hgt.pth" \
  --log_dir "${REPO}/logs/linelevel_${TAG}" \
  --num_epochs 50 \
  --k_folds 10 \
  --patience 7 \
  --seed 1 \
  --no_progress \
  "$@"
