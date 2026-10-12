#!/usr/bin/env bash
# Train on the labeling_v3 graphs (locally built fused graph + tokenizer ids), reentrancy
# and access_control, with the paper's settings and seeded folds (seed 1).
#   contract level: 5-fold, all contracts. Node labels are not used at this level, so the
#                   clean and author graphs give the same run; it is trained once.
#   line level    : 10-fold, contracts labelled buggy, once per label mode.
# Best (lowest val loss) and last (stopping epoch) weights are both scored at the end.
set -uo pipefail
PY=/home/zhao/miniconda3/envs/mando/bin/python
cd /home/zhao/SmartContract/ge-sc-llm
ART=Test_code/labeling_v3/artifacts/v1
RUNS=Test_code/labeling_v3/runs/v1
SUMMARY="$RUNS/summary.txt"
mkdir -p "$RUNS"
: > "$SUMMARY"

label_file() {
  if [ "$1" = reentrancy ]; then echo experiments/ge-sc-data/source_code/reentrancy/graph_labels.json
  else echo scripts/access_control_test/artifacts/dataset_a_source_range_v1/graph_labels.json; fi
}

for BUG in reentrancy access_control; do
  LABEL=$(label_file "$BUG")
  for MODE in clean author; do
    [ -f "$ART/$BUG/linelevel_tok_${MODE}.gpickle" ] || "$PY" -B Test_code/labeling_v3/make_linelevel.py \
      --graph "$ART/$BUG/hcg_tok_${MODE}.gpickle" --contract_labels "$LABEL" \
      --output "$ART/$BUG/linelevel_tok_${MODE}.gpickle" | tee -a "$SUMMARY"
  done

  OUT="$RUNS/$BUG/contract"; mkdir -p "$OUT"
  "$PY" -u -B graph_classifier.py --bug_type "$BUG" \
    --compressed_graph "$ART/$BUG/hcg_tok_author.gpickle" --label "$LABEL" \
    --node_feature inside_token --output_models "$OUT/${BUG}_hgt.pth" --log_dir "$OUT/tensorboard" \
    --num_epochs 50 --k_folds 5 --patience 7 --seed 1 --no_progress --verbose_epochs > "$OUT/train.log" 2>&1
  echo "### $BUG contract level" | tee -a "$SUMMARY"
  "$PY" -B scripts/eval_best_last.py --task contract --graph "$ART/$BUG/hcg_tok_author.gpickle" \
    --run_dir "$OUT" --label "$LABEL" 2>&1 | grep -E '^fold|^best|^last|Error' | tee -a "$SUMMARY"

  for MODE in clean author; do
    OUT="$RUNS/$BUG/line_$MODE"; mkdir -p "$OUT"
    "$PY" -u -B node_classifier.py --bug_type "$BUG" \
      --compressed_graph "$ART/$BUG/linelevel_tok_${MODE}.gpickle" \
      --node_feature inside_token --output_models "$OUT/${BUG}_hgt.pth" --log_dir "$OUT/tensorboard" \
      --num_epochs 50 --k_folds 10 --patience 7 --seed 1 --split_by contract \
      --no_progress --verbose_epochs > "$OUT/train.log" 2>&1
    echo "### $BUG line level, labels=$MODE" | tee -a "$SUMMARY"
    "$PY" -B scripts/eval_best_last.py --task line --graph "$ART/$BUG/linelevel_tok_${MODE}.gpickle" \
      --run_dir "$OUT" 2>&1 | grep -E '^fold|^best|^last|Error' | tee -a "$SUMMARY"
  done
done
echo DONE | tee -a "$SUMMARY"
