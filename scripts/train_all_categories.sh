#!/usr/bin/env bash
# Train contract level (Phase 1) and line level (Phase 2) for several categories,
# on the graphs written by `python -m scripts.graph_build`.
#
# Usage: train_all_categories.sh [inside_token|nodetype] [category ...]
#   feature   inside_token (default; tokenizer features, the MANDO-LLM method)
#             or nodetype (structure-only baseline)
#   category  defaults to all seven
#
# Same arguments as scripts/train_contractlevel.sh / scripts/train_linelevel.sh (the
# paper's settings: 5 / 10 folds, patience 7, 50 epochs, seed 1), which are left
# unchanged because sealed manifests pin them and they hard-code /home/zhao + conda.
#
# Environment: NUM_EPOCHS, CONTRACT_K_FOLDS (5), LINE_K_FOLDS (10), K_FOLDS (sets
# both), SEED, PHASES ("contract line"), SCHEME (ids), TOKENIZER_TAG (codet5p-770m),
# PYTHON (python). Extra classifier flags can go in EXTRA_ARGS. A failing run stops
# everything (set -e), so a broken graph never yields a half-filled results table.
set -eu

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FEATURE="${1:-inside_token}"
if [ "$#" -gt 0 ]; then shift; fi
CATEGORIES=("$@")
if [ "${#CATEGORIES[@]}" -eq 0 ]; then
  CATEGORIES=(access_control arithmetic denial_of_service front_running
              reentrancy time_manipulation unchecked_low_level_calls)
fi
PYTHON="${PYTHON:-python}"
PHASES="${PHASES:-contract line}"
SCHEME="${SCHEME:-ids}"
TOKENIZER_TAG="${TOKENIZER_TAG:-codet5p-770m}"
NUM_EPOCHS="${NUM_EPOCHS:-50}"
CONTRACT_K_FOLDS="${K_FOLDS:-${CONTRACT_K_FOLDS:-5}}"
LINE_K_FOLDS="${K_FOLDS:-${LINE_K_FOLDS:-10}}"
SEED="${SEED:-1}"
read -r -a EXTRA <<< "${EXTRA_ARGS:-}"

case "${FEATURE}" in
  inside_token)
    CONTRACT_GRAPH="tokenizer_${SCHEME}_${TOKENIZER_TAG}_hcg_compressed_graphs.gpickle"
    LINE_GRAPH="linelevel_tokenizer_${SCHEME}.gpickle"
    TAG="tok_${SCHEME}" ;;
  nodetype)
    CONTRACT_GRAPH="hcg_compressed_graphs.gpickle"
    LINE_GRAPH="linelevel_hcg.gpickle"
    TAG="hcg_nodetype" ;;
  *) echo "unknown feature '${FEATURE}' (inside_token|nodetype)" >&2; exit 2 ;;
esac

cd "${REPO}"
for CATEGORY in "${CATEGORIES[@]}"; do
  BASE="${REPO}/experiments/ge-sc-data/source_code/${CATEGORY}"
  for f in "${BASE}/${CONTRACT_GRAPH}" "${BASE}/${LINE_GRAPH}" "${BASE}/graph_labels.json"; do
    if [ ! -f "${f}" ]; then
      echo "missing ${f}; run: python -m scripts.graph_build --categories ${CATEGORY}" >&2
      exit 1
    fi
  done
  for PHASE in ${PHASES}; do
    echo "=================== ${CATEGORY} / ${PHASE} / ${FEATURE} ==================="
    if [ "${PHASE}" = contract ]; then
      "${PYTHON}" -u graph_classifier.py \
        --compressed_graph "${BASE}/${CONTRACT_GRAPH}" \
        --label "${BASE}/graph_labels.json" \
        --dataset "${BASE}/source_files" --testset "${BASE}/source_files" \
        --node_feature "${FEATURE}" \
        --output_models "${REPO}/models/contractlevel/${TAG}/${CATEGORY}_hgt.pth" \
        --log_dir "${REPO}/logs/contractlevel_${TAG}/${CATEGORY}" \
        --num_epochs "${NUM_EPOCHS}" --k_folds "${CONTRACT_K_FOLDS}" \
        --patience 7 --seed "${SEED}" --no_progress ${EXTRA[@]+"${EXTRA[@]}"}
    elif [ "${PHASE}" = line ]; then
      "${PYTHON}" -u node_classifier.py \
        --compressed_graph "${BASE}/${LINE_GRAPH}" \
        --dataset "${BASE}/source_files" --testset "${BASE}/source_files" \
        --node_feature "${FEATURE}" \
        --output_models "${REPO}/models/linelevel/${TAG}/${CATEGORY}_hgt.pth" \
        --log_dir "${REPO}/logs/linelevel_${TAG}/${CATEGORY}" \
        --num_epochs "${NUM_EPOCHS}" --k_folds "${LINE_K_FOLDS}" \
        --patience 7 --seed "${SEED}" --no_progress ${EXTRA[@]+"${EXTRA[@]}"}
    else
      echo "unknown phase '${PHASE}' (contract|line)" >&2; exit 2
    fi
  done
done
