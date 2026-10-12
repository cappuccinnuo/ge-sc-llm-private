#!/usr/bin/env bash
# Re-run the two line-level configs whose stdout was lost when the batch job was
# backgrounded, and tee everything to a file this time.
set -u
REPO=/home/zhao/SmartContract/ge-sc-llm
BASE="${REPO}/experiments/ge-sc-data/source_code/reentrancy"
OUT="${REPO}/outputs/linelevel_results.txt"
mkdir -p "$(dirname "${OUT}")"

{
  for spec in "linelevel_hcg.gpickle nodetype hcg_nodetype" \
              "linelevel_tokenizer_ids.gpickle inside_token tok_ids"; do
    set -- ${spec}
    echo "############################################################"
    echo "# $3   feature=$2"
    echo "############################################################"
    bash "${REPO}/scripts/train_linelevel.sh" "${BASE}/$1" "$2" "$3" 2>&1 \
      | grep -E "Contracts in graph|Buggy node |Average (Buggy|Macro)"
    echo
  done
} | tee -a "${OUT}"

echo "results appended to ${OUT}"
