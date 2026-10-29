# Prompt 8E: N-real candidate and leakage acceptance

Status: **stopped at preregistered leakage gates**. No HGT model construction,
forward, optimizer update or formal training was executed by this workflow.
P3 performs 15 small CPU logistic-regression fits (three views, five grouped
folds); these are diagnostic classifiers, not the proposed 170 HGT fits.

See [PROMPT8E_REPORT.md](../PROMPT8E_REPORT.md) for actual results.
Historical 8D code, plan/seal, folds and features remain unchanged. Supersession
is recorded only in the new batch's naming/supersession.json.

## Modules

- real_names.py: seven syntax-role pools, declaration witnesses, lexical
  occurrence weights, deterministic SHA-derived sampling without file collisions.
- prepare_real.py: bind the 128 sources, A_v2 scopes and archived folds;
  freeze names and probe protocol before scoring; run P1/P2/P3 and keyword rules.
- rename_parity.py: approved code-only temporary HCG copies; reuse frozen
  L1/L2/L3 analyzers and compare archived/original/renamed facts and endpoints.
- leakage_probes.py: P2 inner-train-only name memory; P3 grouped character LR.
- acceptance_real.py: independent confusion/rank-AUC recount; sealed blocked
  acceptance decision and non-authorizing template.

No general Solidity alpha-conversion/type checker is claimed. Grammar
acceptance and bounded analyzer parity are not compiler/ABI equivalence.
The pool uses all 128 identities as requested, including held-out vocabulary.
It does not inspect labels when constructing names.

## Actual environment and commands

Existing WSL Ubuntu-22.04 mando environment; Python 3.7.12. No dependency or
compiler installation. All commands run from /home/zhao/SmartContract/ge-sc-llm-ddg-v11.

    conda activate mando
    export PYTHONDONTWRITEBYTECODE=1
    export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
    export CUDA_VISIBLE_DEVICES=''
    export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64

The following output directories already exist and commands reject overwrites.
These show the exact preparation operations; do not rerun to search for a
better mapping after observing failed gates.

    python -B -m scripts.DFG.dfg_v2.benchmark_v2.prepare_real names \
      --old-plan scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F/plan.json \
      --scope scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/A_v2/stratification.json \
      --output scripts/DFG/experiments/artifacts/dfg_v2/prompt8e_v1/naming

    python -B -m scripts.DFG.dfg_v2.benchmark_v2.rename_parity \
      --naming scripts/DFG/experiments/artifacts/dfg_v2/prompt8e_v1/naming \
      --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json \
      --output scripts/DFG/experiments/artifacts/dfg_v2/prompt8e_v1/semantic_parity

    python -B -m scripts.DFG.dfg_v2.benchmark_v2.prepare_real probes \
      --naming scripts/DFG/experiments/artifacts/dfg_v2/prompt8e_v1/naming \
      --output scripts/DFG/experiments/artifacts/dfg_v2/prompt8e_v1/probes

Acceptance was finalized through the same module's Python API; its equivalent
CLI (also refuses overwrite) is:

    python -B -m scripts.DFG.dfg_v2.benchmark_v2.acceptance_real \
      --naming scripts/DFG/experiments/artifacts/dfg_v2/prompt8e_v1/naming \
      --probes scripts/DFG/experiments/artifacts/dfg_v2/prompt8e_v1/probes \
      --semantics scripts/DFG/experiments/artifacts/dfg_v2/prompt8e_v1/semantic_parity \
      --output scripts/DFG/experiments/artifacts/dfg_v2/prompt8e_v1/acceptance

Read-only score verification (no probe refit or resampling):

    python -B -c "from scripts.DFG.dfg_v2.benchmark_v2.acceptance_real import verify_results; print(verify_results('scripts/DFG/experiments/artifacts/dfg_v2/prompt8e_v1/naming', 'scripts/DFG/experiments/artifacts/dfg_v2/prompt8e_v1/probes'))"

Tests actually executed, with logs in prompt8e_v1:

    python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests/test_prompt8e_real_names.py
    python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
    python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests/test_prompt8e_acceptance.py
    python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py

The full v2 run contained 2,447 tests including the first 27 new tests. The 8
subsequently added acceptance tests passed separately: 2,455 unique v2 tests,
plus 223 old tests, total 2,678. Warnings: 8 in full v2 and 29 in legacy, existing
DGL/NetworkX deprecations. Initial 24/27 targeted results are not counted twice.

## Stop boundary

P1 N-real: 872/872 replacement spellings witnessed in ordinary code.
P2 N-real AC exceeds all-positive BF1 by 9.46699 / 9.36127 pp (orig/C1),
above 5 pp. P3 N-real AUC 0.643159 exceeds 0.60.

No new NPZ feature view, token re-encoding/equivalence test, N-anon view or
ready 170-fit execution plan was created. This is intentional enforcement of
the prompt's stop rule, not a claim those steps passed. The acceptance seal
seals a failed decision; it is not a training-plan seal. Future redesign,
labels/seeds/location and actual execution require a new agreed plan. No
automatic change to the thresholds, random seed, name pool or old results.
