#!/usr/bin/env bash
# Train the node-level (line-level) HGT classifier on the rebuilt reentrancy graph.
#
# Usage:
#   scripts/train_node.sh [epochs] [folds] [output.pth] [extra args...]
#
# Progress:
#   default            -> one tqdm bar per fold, live loss/F1 in the postfix
#   --verbose_epochs   -> one printed line per epoch instead of the bar
#   --no_progress      -> neither (quiet, fold-level output only)
#
# TensorBoard scalars land in logs/node_classification unless --non_visualize:
#   tensorboard --logdir logs/node_classification
set -eu

REPO="/home/zhao/SmartContract/ge-sc-llm"
EPOCHS="${1:-50}"
FOLDS="${2:-5}"
OUT="${3:-${REPO}/models/node_detection/nodetype/reentrancy_hgt.pth}"
if [ "$#" -gt 3 ]; then shift 3; else shift "$#"; fi

export TREE_SITTER_LIB_DIR="${REPO}/build/linux-x86_64"
source /home/zhao/miniconda3/etc/profile.d/conda.sh
conda activate mando
cd "${REPO}"

python node_classifier.py \
  --compressed_graph "${REPO}/experiments/ge-sc-data/source_code/reentrancy/cfg_compressed_graphs.gpickle" \
  --dataset "${REPO}/experiments/ge-sc-data/source_code/reentrancy/source_files" \
  --testset "${REPO}/experiments/ge-sc-data/source_code/reentrancy/source_files" \
  --node_feature nodetype \
  --output_models "${OUT}" \
  --log_dir "${REPO}/logs/node_classification" \
  --num_epochs "${EPOCHS}" \
  --k_folds "${FOLDS}" \
  --patience 7 \
  --seed 1 \
  "$@"
