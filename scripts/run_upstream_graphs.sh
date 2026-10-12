#!/usr/bin/env bash
# Train on the authors' own graphs, so the construction side is taken out of the picture.
#
# Everything else is unchanged: same tokenizer scheme (ids, 512-dim), same HGT, same
# fold counts and hyperparameters. If these runs land near the paper's Table 5 figure
# for reentrancy (96.78 line level), the gap we have been chasing lives in graph
# construction; if they do not, it lives in training or features instead.
set -eu
source /home/zhao/miniconda3/etc/profile.d/conda.sh
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm
BASE=experiments/ge-sc-data/source_code/reentrancy
LAB=data/upstream_mando_llm/graph_detection/reentrancy_graph_labels.json
OUT=outputs/upstream_graph_results.txt
mkdir -p outputs

{
echo "=========== tokenizer features on the authors' graphs ==========="
TRANSFORMERS_OFFLINE=1 python scripts/encode_tokenizer_features.py \
  --graph "${BASE}/upstream_linelevel_cfg.gpickle" --scheme ids \
  --output "${BASE}/upstream_linelevel_tok.gpickle" 2>&1 \
  | tr '\r' '\n' | grep -E "^nodes|^token lengths|^wrote node-level"
TRANSFORMERS_OFFLINE=1 python scripts/encode_tokenizer_features.py \
  --graph "${BASE}/upstream_contractlevel_cfg_cg.gpickle" --scheme ids \
  --output "${BASE}/upstream_contractlevel_tok.gpickle" 2>&1 \
  | tr '\r' '\n' | grep -E "^nodes|^token lengths|^wrote node-level"

echo
echo "=========== LINE LEVEL (authors' CFG, 71 buggy contracts, 10-fold) ==========="
echo "--- nodetype ---"
bash scripts/train_linelevel.sh "${BASE}/upstream_linelevel_cfg.gpickle" \
  nodetype up_line_nodetype 2>&1 \
  | grep -E "Buggy node |Split mode:|Average (Buggy|Macro) F1"
echo "--- tokenizer ids (the paper's method) ---"
bash scripts/train_linelevel.sh "${BASE}/upstream_linelevel_tok.gpickle" \
  inside_token up_line_tok 2>&1 \
  | grep -E "Buggy node |Split mode:|Average (Buggy|Macro) F1"

echo
echo "=========== CONTRACT LEVEL (authors' CFG+CG, 142 contracts, 5-fold) ==========="
echo "--- nodetype ---"
bash scripts/train_contractlevel.sh "${BASE}/upstream_contractlevel_cfg_cg.gpickle" \
  nodetype up_graph_nodetype --label "${LAB}" 2>&1 \
  | grep -E "Etype dict|Average (Buggy|Macro) F1"
echo "--- tokenizer ids (the paper's method) ---"
bash scripts/train_contractlevel.sh "${BASE}/upstream_contractlevel_tok.gpickle" \
  inside_token up_graph_tok --label "${LAB}" 2>&1 \
  | grep -E "Etype dict|Average (Buggy|Macro) F1"
} | tee -a "${OUT}"

echo
echo "paper Table 5, reentrancy line level: MANDO-HGT 85.06 | Codet5p-770m 96.78"
echo "results appended to ${OUT}"
