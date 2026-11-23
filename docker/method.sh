#!/usr/bin/env bash
# The proposed method (FULL = DFG G3R + NodeSem S6 + EdgeSem G4R-AC) against the MANDO-LLM
# baseline (G0) on Dataset B, grouped protocol, several seeds, inside the image:
#
#   QUICK=1 docker/run.sh docker/method.sh     # plumbing: time_manipulation, fold 0, 2 epochs, 1 seed
#   docker/run.sh docker/method.sh             # all 7 categories, seeds 1 2 3; run inside tmux
#
# 1. environment check and the unit tests;
# 2. the pinned sources and models (`hcg fetch`), then every stage regenerated from the
#    Solidity sources into the run directory: hcg graphs (CodeT5+ tokens), dfg L1-L3,
#    nodesem analysis + CodeT5+ vectors + Qwen descriptions + BGE teacher vectors, edgesem
#    F4 edges and attributes;
# 3. per seed, `python -m benchmark run --protocols grouped --profiles G0 FULL`: contract,
#    line and cascade tracks with both profiles on the same project-grouped folds;
# 4. `python -m combined compare`: FULL vs G0 paired over (seed, fold), DAppSCAN line level
#    first -> compare.md / compare.json.
#
# Settings (environment): NAME (run directory under runs/method, default b or quick),
# CATEGORIES (default all), SEEDS (default "1 2 3"), WORKERS (describe processes, each with
# its own model copy of ~3 GB GPU memory; default 4). Every finished stage leaves a marker
# in the run directory, every finished LLM response and fit its sealed file, so rerunning
# the same command after an interruption resumes where it stopped (an LLM unit cut off
# mid-generation is generated again from scratch).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export MANDO_DATA_DIR="${MANDO_DATA_DIR:-$PWD/data}"
DATASET=B
if [ "${QUICK:-0}" = 1 ]; then
    NAME="${NAME:-quick}"; CATEGORIES="${CATEGORIES:-time_manipulation}"; SEEDS="${SEEDS:-1}"
    EXTRA="--folds 0 --epochs 2 --partial-teacher"; DESCRIBE="--limit 200"
else
    NAME="${NAME:-b}"; CATEGORIES="${CATEGORIES:-all}"; SEEDS="${SEEDS:-1 2 3}"; EXTRA=""; DESCRIBE=""
fi
WORKERS="${WORKERS:-4}"
OUT="runs/method/$NAME"
mkdir -p "$OUT/.done"
LOG="$OUT/method.log"
exec > >(tee -a "$LOG") 2>&1

step() {
    local name="$1" start=$SECONDS
    shift
    echo; echo "=== $name"
    "$@"
    echo "--- $name: $((SECONDS - start)) s"
}

once() {          # once <marker> <name> <command...>: skip a stage that already finished
    local marker="$OUT/.done/$1"
    shift
    if [ -f "$marker" ]; then echo; echo "=== $1: done earlier"; return; fi
    step "$@"
    touch "$marker"
}

if [ "$CATEGORIES" = all ]; then
    LIST=$(python -c "from hcg.datasets import get_dataset; print(' '.join(c.name for c in get_dataset('$DATASET').categories))")
else
    LIST="$CATEGORIES"
fi
C="--dataset $DATASET --categories $LIST"
STORES="--hcg $OUT/hcg --dfg $OUT/dfg"

step "environment" python docker/check_env.py
step "unit tests" python -m pytest -q tests/hcg/test_units.py tests/hcg/test_dataset_b.py tests/dfg/test_units.py \
    tests/dfg/test_train.py tests/nodesem/test_units.py tests/edgesem/test_units.py tests/combined tests/benchmark \
    -k "not recomposing and not build_labels"
once fetch "fetch sources and pinned models" python -m hcg fetch --dataset "$DATASET"
# shellcheck disable=SC2086
once hcg "hcg build ($LIST)" python -m hcg build $C --out "$OUT/hcg"
# shellcheck disable=SC2086
once dfg "dfg build" python -m dfg build $C --hcg "$OUT/hcg" --out "$OUT/dfg"
# shellcheck disable=SC2086
once nodesem_analyze "nodesem analyze" python -m nodesem analyze $C $STORES --nodesem "$OUT/nodesem"
# shellcheck disable=SC2086
once nodesem_encode "nodesem encode (CodeT5+)" python -m nodesem encode $C $STORES --nodesem "$OUT/nodesem"
# shellcheck disable=SC2086
once nodesem_describe "nodesem describe (Qwen2.5-Coder-3B)" python -u -m nodesem describe $C $STORES \
    --nodesem "$OUT/nodesem" --workers "$WORKERS" $DESCRIBE
# shellcheck disable=SC2086
once nodesem_teacher "nodesem encode --teacher (BGE)" python -m nodesem encode $C $STORES --nodesem "$OUT/nodesem" --teacher
# shellcheck disable=SC2086
once edgesem "edgesem build" python -m edgesem build $C $STORES --edgesem "$OUT/edgesem"

RUNS=""
for SEED in $SEEDS; do
    # shellcheck disable=SC2086
    step "benchmark: G0 and FULL, grouped, seed $SEED" python -u -m benchmark run $C $STORES \
        --nodesem "$OUT/nodesem" --edgesem "$OUT/edgesem" --out "$OUT/seed_$SEED" \
        --protocols grouped --profiles G0 FULL --seed "$SEED" $EXTRA
    RUNS="$RUNS $OUT/seed_$SEED"
done
# shellcheck disable=SC2086
step "compare FULL with G0" python -m combined compare --dataset "$DATASET" --categories $LIST --hcg "$OUT/hcg" \
    --runs $RUNS --out "$OUT"

echo; nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv
echo "method ok; comparison: $OUT/compare.md; per seed: $OUT/seed_*/report.md; log: $LOG"
