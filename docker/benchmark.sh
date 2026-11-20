#!/usr/bin/env bash
# The whole pipeline from source to final detection, compared with the MANDO-LLM paper,
# inside the image:
#
#   docker/run.sh docker/benchmark.sh                 # 7 categories, every protocol, G0
#   QUICK=1 docker/run.sh docker/benchmark.sh         # plumbing check: 1 category, fold 0, 2 epochs
#   DATASET=B docker/run.sh docker/benchmark.sh       # the same on Dataset B (paper Tables 4 and 6)
#
# 1. environment check and the unit tests;
# 2. pinned label repositories and models (`hcg fetch`), then the graphs of every category
#    rebuilt from the Solidity sources (`hcg build`, CodeT5+ tokens, checked against the
#    paper's Table 1 and the authors' released graphs) into the run directory;
# 3. `python -m benchmark run`: the MANDO-LLM baseline (G0) at contract and line level under
#    the paper's protocol and the grouped protocol, the two-phase detector (contract model ->
#    line model) and the authors' own trainers; then evaluation.json, report.md, findings/.
#
# Settings (environment): DATASET (A or B, default A),
# NAME (run directory under runs/benchmark, default full or quick; with a _b suffix for B),
# CATEGORIES (default all), PROTOCOLS (default "paper grouped upstream").
# The run directory holds its own graphs (hcg/), built once: an interrupted run resumes
# where it stopped when the same command is rerun; REBUILD=1 rebuilds the graphs (only
# for a new NAME, since a run refuses to mix graphs).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export MANDO_DATA_DIR="${MANDO_DATA_DIR:-$PWD/data}"
PROTOCOLS="${PROTOCOLS:-paper grouped upstream}"
DATASET="${DATASET:-A}"
SUFFIX=$([ "$DATASET" = A ] && echo "" || echo "_$(echo "$DATASET" | tr 'A-Z' 'a-z')")
if [ "${QUICK:-0}" = 1 ]; then
    NAME="${NAME:-quick$SUFFIX}"; CATEGORIES="${CATEGORIES:-reentrancy}"; EXTRA="--folds 0 --epochs 2"
else
    NAME="${NAME:-full$SUFFIX}"; CATEGORIES="${CATEGORIES:-all}"; EXTRA=""
fi
OUT="runs/benchmark/$NAME"
HCG="$OUT/hcg"
mkdir -p "$OUT"
LOG="$OUT/benchmark.log"
exec > >(tee -a "$LOG") 2>&1

step() {
    local name="$1" start=$SECONDS
    shift
    echo; echo "=== $name"
    "$@"
    echo "--- $name: $((SECONDS - start)) s"
}

step "environment" python docker/check_env.py
step "unit tests" python -m pytest -q tests/hcg/test_units.py tests/hcg/test_dataset_b.py tests/dfg/test_units.py \
    tests/dfg/test_train.py tests/mando tests/benchmark -k "not recomposing and not build_labels"
step "fetch label repositories and pinned models" python -m hcg fetch --dataset "$DATASET"
if [ "$CATEGORIES" = all ]; then
    LIST=$(python -c "from hcg.datasets import get_dataset; print(' '.join(c.name for c in get_dataset('$DATASET').categories))")
else
    LIST="$CATEGORIES"
fi
MISSING=""
for C in $LIST; do
    if [ "${REBUILD:-0}" = 1 ] || [ ! -f "$HCG/$DATASET/$C/manifest.json" ]; then MISSING="$MISSING $C"; fi
done
if [ -n "$MISSING" ]; then
    # shellcheck disable=SC2086
    step "hcg build ($DATASET:$MISSING)" python -m hcg build --dataset "$DATASET" --categories $MISSING --out "$HCG"
else
    echo; echo "=== hcg build: graphs of $LIST already in $HCG"
fi
# shellcheck disable=SC2086
step "benchmark run ($DATASET: $PROTOCOLS)" python -u -m benchmark run --dataset "$DATASET" --out "$OUT" \
    --hcg "$HCG" --dfg "$OUT/dfg" --categories $LIST --protocols $PROTOCOLS $EXTRA

echo; nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv
echo "benchmark ok; report: $OUT/report.md; log: $LOG"
