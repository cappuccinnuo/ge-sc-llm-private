#!/usr/bin/env bash
# Run the line-level phase for every node-feature variant under the paper's settings.
set -u
REPO=/home/zhao/SmartContract/ge-sc-llm
BASE="${REPO}/experiments/ge-sc-data/source_code/reentrancy"

run () {
  local graph="$1"; local feature="$2"; local tag="$3"
  if [ ! -f "${graph}" ]; then
    echo "skip (missing): ${graph}"
    return
  fi
  echo "############################################################"
  echo "# ${tag}   feature=${feature}"
  echo "############################################################"
  bash "${REPO}/scripts/train_linelevel.sh" "${graph}" "${feature}" "${tag}" 2>&1 \
    | grep -E "Contracts in graph|Buggy node |torch.Size|Average (Buggy|Macro)"
  echo
}

run "${BASE}/linelevel_hcg.gpickle"              nodetype     hcg_nodetype
run "${BASE}/linelevel_tokenizer_ids.gpickle"    inside_token tok_ids
run "${BASE}/linelevel_tokenizer_ids_norm.gpickle" inside_token tok_ids_norm
run "${BASE}/linelevel_tokenizer_hashed_bow.gpickle" inside_token tok_hashed_bow
