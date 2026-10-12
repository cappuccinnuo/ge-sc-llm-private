#!/usr/bin/env bash
# Rebuild the full chain with add_dummy_edges off (the new default, and the
# repository's original state), then train line-level on it.
#
# Nothing else changes: same corpus, same annotations, same tokenizer scheme, same
# 10-fold / 50-epoch / patience-7 / seed-1 settings. The only difference from the
# numbers in HANDOVER.md section 5 is the 3,981 'recursive_method_call' edges, which
# every measurement shows are contract-to-function containment rather than calls.
set -eu
source /home/zhao/miniconda3/etc/profile.d/conda.sh
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm
export TREE_SITTER_LIB_DIR=$PWD/build/linux-x86_64
BASE=experiments/ge-sc-data/source_code/reentrancy
OUT=outputs/no_dummy_results.txt
mkdir -p outputs

# make sure the switch really is off for this build
unset MANDO_DUMMY_EDGES || true

{
echo "=========== 1. CFGs without dummy edges ==========="
python -m scripts.gen_reentrancy_cfg \
  --source_dir "${BASE}/source_files" \
  --output_dir /tmp/reentrancy_nodummy 2>&1 | grep -E "^Found|^Generated"
python scripts/inspect_regen.py /tmp/reentrancy_nodummy 2>&1 \
  | grep -E "total nodes|total edges"

echo
echo "=========== 2. labels ==========="
python scripts/build_labeled_graph.py \
  --cfg_dir /tmp/reentrancy_nodummy \
  --output "${BASE}/hcg_nodummy.gpickle" 2>&1 \
  | grep -E "contracts with|buggy nodes"

echo
echo "=========== 3. tokenizer features ==========="
TRANSFORMERS_OFFLINE=1 python scripts/encode_tokenizer_features.py \
  --graph "${BASE}/hcg_nodummy.gpickle" --scheme ids \
  --output "${BASE}/tokenizer_ids_nodummy.gpickle" 2>&1 \
  | tr '\r' '\n' | grep -E "^wrote node-level"

echo
echo "=========== 4. line-level subgraph ==========="
python scripts/filter_buggy_contracts.py \
  --graph "${BASE}/tokenizer_ids_nodummy.gpickle" \
  --output "${BASE}/linelevel_nodummy.gpickle" 2>&1 \
  | grep -E "output:|buggy nodes|edge types"

echo
echo "=========== 5. train, contract split (paper's method) ==========="
bash scripts/train_linelevel.sh "${BASE}/linelevel_nodummy.gpickle" \
  inside_token nodummy_contract 2>&1 \
  | grep -E "Buggy node |Split mode:|Average (Buggy|Macro) F1"

echo
echo "=========== 6. train, snippet split (dedup control) ==========="
bash scripts/train_linelevel.sh "${BASE}/linelevel_nodummy.gpickle" \
  inside_token nodummy_snippet --split_by snippet 2>&1 \
  | grep -E "Buggy node |Split mode:|Average (Buggy|Macro) F1"
} | tee -a "${OUT}"

echo "results appended to ${OUT}"
