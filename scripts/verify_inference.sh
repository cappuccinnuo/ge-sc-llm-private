#!/usr/bin/env bash
# Confirm both detection phases actually run in --test mode against the artifacts
# we produced, rather than assuming the code path works because it exists.
set -u
REPO=/home/zhao/SmartContract/ge-sc-llm
BASE="${REPO}/experiments/ge-sc-data/source_code/reentrancy"

source /home/zhao/miniconda3/etc/profile.d/conda.sh
conda activate mando
cd "${REPO}"

echo "############ Phase 1: contract-level detection ############"
python graph_classifier.py --test \
  --compressed_graph "${BASE}/tokenizer_ids_codet5p-770m_hcg_compressed_graphs.gpickle" \
  --label "${BASE}/graph_labels.json" \
  --testset "${BASE}/source_files" \
  --node_feature inside_token \
  --checkpoint "${REPO}/models/contractlevel/tok_ids/reentrancy_hgt.pth" 2>&1 \
  | grep -vE "^Using backend|torch.Size" | tail -20

echo
echo "############ Phase 2: line-level detection ############"
python node_classifier.py --test \
  --compressed_graph "${BASE}/linelevel_tokenizer_ids.gpickle" \
  --testset "${BASE}/source_files" \
  --node_feature inside_token \
  --checkpoint "${REPO}/models/linelevel/tok_ids/reentrancy_hgt.pth" 2>&1 \
  | grep -vE "^Using backend|torch.Size" | tail -25
