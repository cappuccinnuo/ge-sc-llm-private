#!/usr/bin/env bash
# Line-level training under both fold-splitting schemes, results tee'd for comparison.
#
#   contract  original behaviour: split the contract list, then expand to nodes.
#             A snippet can sit on both sides, and 76.5% of validation nodes turn out
#             to share an exact (code, label) pair with their training fold.
#   snippet   group nodes by their exact source text and keep each group whole, so
#             that overlap drops to 0%.
#
# Both runs use the same graph, epochs, folds, patience and seed, so the gap between
# them is the part of the score that came from repeated code rather than from the model.
set -u
REPO=/home/zhao/SmartContract/ge-sc-llm
BASE="${REPO}/experiments/ge-sc-data/source_code/reentrancy"
GRAPH="${BASE}/linelevel_tokenizer_ids.gpickle"
OUT="${REPO}/outputs/split_comparison.txt"
mkdir -p "$(dirname "${OUT}")"

source /home/zhao/miniconda3/etc/profile.d/conda.sh
conda activate mando
cd "${REPO}"

run () {
  local mode="$1"
  echo "############################################################"
  echo "# split_by = ${mode}"
  echo "############################################################"
  python node_classifier.py \
    --compressed_graph "${GRAPH}" \
    --dataset "${BASE}/source_files" \
    --testset "${BASE}/source_files" \
    --node_feature inside_token \
    --output_models "${REPO}/models/split_${mode}/reentrancy_hgt.pth" \
    --log_dir "${REPO}/logs/split_${mode}" \
    --num_epochs 50 --k_folds 10 --patience 7 --seed 1 \
    --no_progress --split_by "${mode}" 2>&1 \
    | grep -E "Buggy node |Split mode:|Average (Buggy|Macro) F1"
  echo
}

{
  run contract
  run snippet
} | tee -a "${OUT}"

echo "results appended to ${OUT}"
