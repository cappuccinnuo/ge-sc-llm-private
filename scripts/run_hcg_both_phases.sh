#!/usr/bin/env bash
# Both phases on the fused CFG+CG heterogeneous contract graph, as section 4.5 describes.
#
# The paper's method section says Phase 2 classifies "the node embeddings of their
# heterogeneous contract graphs", i.e. the fused graph, while section 5.1 says the
# line-level task "focuses exclusively on the buggy contracts". So the line-level input
# here is the authors' CFG+CG graph restricted to its 71 buggy contracts, rather than
# the separate CFG-only file they shipped under node_detection.
#
#   Phase 1  authors' CFG+CG, 142 contracts, 5-fold
#   Phase 2  same graph filtered to 71 buggy contracts, 10-fold
set -eu
source /home/zhao/miniconda3/etc/profile.d/conda.sh
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm
BASE=experiments/ge-sc-data/source_code/reentrancy
LAB=data/upstream_mando_llm/graph_detection/reentrancy_graph_labels.json
OUT=outputs/hcg_both_phases.txt
mkdir -p outputs

{
echo "=========== 1. line-level input: HCG restricted to buggy contracts ==========="
python scripts/filter_buggy_contracts.py \
  --graph "${BASE}/upstream_contractlevel_cfg_cg.gpickle" \
  --output "${BASE}/upstream_linelevel_hcg.gpickle" 2>&1 \
  | grep -E "input:|contracts|output:|buggy nodes|edge types|node types"

echo
echo "=========== 2. tokenizer features for the line-level HCG ==========="
TRANSFORMERS_OFFLINE=1 python scripts/encode_tokenizer_features.py \
  --graph "${BASE}/upstream_linelevel_hcg.gpickle" --scheme ids \
  --output "${BASE}/upstream_linelevel_hcg_tok.gpickle" 2>&1 \
  | tr '\r' '\n' | grep -E "^nodes|^wrote node-level"

echo
echo "=========== 3. PHASE 2 line level on HCG (10-fold, buggy only) ==========="
echo "--- nodetype ---"
bash scripts/train_linelevel.sh "${BASE}/upstream_linelevel_hcg.gpickle" \
  nodetype hcg_line_nodetype 2>&1 \
  | grep -E "Buggy node |Split mode:|Average (Buggy|Macro) F1"
echo "--- tokenizer ids ---"
bash scripts/train_linelevel.sh "${BASE}/upstream_linelevel_hcg_tok.gpickle" \
  inside_token hcg_line_tok 2>&1 \
  | grep -E "Buggy node |Split mode:|Average (Buggy|Macro) F1"

echo
echo "=========== 4. PHASE 1 contract level on HCG (5-fold, 142 contracts) ==========="
echo "(already measured: nodetype 88.23 / tokenizer 87.72 - repeated here for one table)"
} | tee -a "${OUT}"

echo
echo "paper Table 5 reentrancy line level, codet5p-770m: 96.78"
echo "results appended to ${OUT}"
