#!/usr/bin/env bash
# GPU smoke run of the whole pipeline on one category, inside the image:
#
#   docker/run.sh docker/smoke.sh [category]          # default: access_control
#
# 1. environment check (GPU, PyTorch for sm_120, DGL GPU kernels, grammar, llama.cpp);
# 2. unit tests, then the Dataset A tests of the category: on the new PyTorch/DGL stack
#    the stages must still equal the authors' graphs, the pre-restructure code and the
#    sealed evidence (SKIP_DATASET_TESTS=1 skips this, ~30-60 min);
# 3. every stage on the category with fold 0 and 2 epochs, timed, written under
#    runs/smoke/ (data/ stays untouched for the full run).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
CAT="${1:-access_control}"
OUT="${SMOKE_OUT:-runs/smoke}"
# The label repositories `hcg fetch` checks out; the CLIs default to data/, the dataset
# tests need it set explicitly (without it they skip).
export MANDO_DATA_DIR="${MANDO_DATA_DIR:-$PWD/data}"
ROOTS="--hcg $OUT/hcg --dfg $OUT/dfg"
mkdir -p "$OUT"
LOG="$OUT/smoke_$CAT.log"
exec > >(tee -a "$LOG") 2>&1

step() {
    local name="$1" start=$SECONDS
    shift
    echo; echo "=== $name"
    "$@"
    echo "--- $name: $((SECONDS - start)) s"
}

step "environment" python docker/check_env.py
step "unit tests" python -m pytest -q tests/hcg/test_units.py tests/hcg/test_models.py tests/dfg/test_units.py tests/dfg/test_train.py \
    tests/nodesem/test_units.py tests/edgesem/test_units.py tests/mando
step "fetch label repositories and pinned models" python -m hcg fetch
if [ "${SKIP_DATASET_TESTS:-0}" != 1 ]; then
    step "dataset tests can run (label sources at \$MANDO_DATA_DIR)" python -c "
from tests.dfg.test_dataset_a import _ready
reason = _ready()
assert reason is None, reason"
    step "dataset tests ($CAT)" python -m pytest -q tests/hcg/test_dataset_a.py tests/dfg/test_dataset_a.py \
        tests/nodesem/test_dataset_a.py tests/edgesem/test_dataset_a.py -k "$CAT"
fi

step "hcg build" python -m hcg build --categories "$CAT" --out "$OUT/hcg"
B="$OUT/hcg/A/$CAT"
S="experiments/ge-sc-data/source_code/$CAT/source_files"
step "mando baseline (1 epoch, 2 folds, both levels)" bash -c "
    python -u -m mando.graph_classifier --compressed_graph $B/contract_level.gpickle --label $B/graph_labels.json \
        --dataset $S --testset $S --node_feature inside_token --output_models $OUT/mando/c.pth \
        --log_dir $OUT/mando/c --num_epochs 1 --k_folds 2 --seed 1 --no_progress
    python -u -m mando.node_classifier --compressed_graph $B/line_level.gpickle --dataset $S --testset $S \
        --node_feature inside_token --output_models $OUT/mando/n.pth --log_dir $OUT/mando/n \
        --num_epochs 1 --k_folds 2 --seed 1 --no_progress"

step "dfg build" python -m dfg build --categories "$CAT" --hcg "$OUT/hcg" --out "$OUT/dfg"
step "dfg train (G0, G3R; fold 0, 2 epochs)" python -m dfg train --categories "$CAT" $ROOTS \
    --profiles G0 G3R --folds 0 --epochs 2 --out "$OUT/runs/dfg"

NS="--categories $CAT $ROOTS --nodesem $OUT/nodesem"
step "nodesem analyze" python -m nodesem analyze $NS
step "nodesem encode (CodeT5+)" python -m nodesem encode $NS
step "nodesem describe (Qwen2.5-Coder-3B, 5 units)" python -m nodesem describe $NS --tasks node --limit 5
step "nodesem teacher encoder (BGE)" python -c "
from nodesem.encode import encode_teacher
units, vectors = encode_teacher(['reads the balance', 'checks the caller'], 'cuda')
print(len(units), vectors.shape)"
step "nodesem train (S0o, S2, S4; node, fold 0, 2 epochs)" python -m nodesem train $NS --tasks node \
    --configs S0o S2 S4 --folds 0 --epochs 2 --out "$OUT/runs/nodesem"

ES="--categories $CAT $ROOTS --edgesem $OUT/edgesem"
step "edgesem build" python -m edgesem build $ES
step "edgesem train (G3R, G4R-P, G4R-A; fold 0, 2 epochs)" python -m edgesem train $ES \
    --profiles G3R G4R-P G4R-A --folds 0 --epochs 2 --out "$OUT/runs/edgesem"

echo; nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv
echo "smoke run ok; log: $LOG"
