#!/usr/bin/env bash
# Contract-level (Phase 1) across node-feature variants, results tee'd to a file.
set -u
REPO=/home/zhao/SmartContract/ge-sc-llm
BASE="${REPO}/experiments/ge-sc-data/source_code/reentrancy"
OUT="${REPO}/outputs/contractlevel_results.txt"
mkdir -p "$(dirname "${OUT}")"

run () {
  local graph="$1"; local feature="$2"; local tag="$3"
  if [ ! -f "${graph}" ]; then
    echo "skip (missing): ${graph}"
    return
  fi
  echo "############################################################"
  echo "# ${tag}   feature=${feature}"
  echo "############################################################"
  bash "${REPO}/scripts/train_contractlevel.sh" "${graph}" "${feature}" "${tag}" 2>&1 \
    | grep -E "Etype dict|Ntype dict|class distribution|Average (Buggy|Macro)"
  echo
}

{
  run "${BASE}/hcg_compressed_graphs.gpickle" nodetype hcg_nodetype
  run "${BASE}/tokenizer_ids_codet5p-770m_hcg_compressed_graphs.gpickle" inside_token tok_ids
} | tee -a "${OUT}"

echo "results appended to ${OUT}"
