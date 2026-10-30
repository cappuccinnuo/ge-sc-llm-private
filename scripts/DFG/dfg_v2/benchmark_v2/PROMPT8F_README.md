# Prompt 8F — declaration-bound N-anon preparation

This module implements source binding and read-only parity checks, not HGT training.
The accepted current outcome is blocked: 159/256 sources have whole-file binding
fallbacks; another 10 sources have ambiguous synthetic-node code projection.
87 unique sources (132 task/file checks) pass all source-to-graph checks.
No partial population is advertised as a complete N-anon feature view.

Run in the existing mando environment:

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export CUDA_VISIBLE_DEVICES=''
```

The following are the **actual completed commands**. Outputs are exclusive;
do not rerun against these existing directories.

```bash
python -B -m scripts.DFG.dfg_v2.benchmark_v2.prepare_anon names \
  --old-plan scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F/plan.json \
  --old8e-manifest scripts/DFG/experiments/artifacts/dfg_v2/prompt8e_v1/naming/manifest.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt8f_v1/naming

python -B -m scripts.DFG.dfg_v2.benchmark_v2.prepare_anon semantic \
  --naming scripts/DFG/experiments/artifacts/dfg_v2/prompt8f_v1/naming \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt8f_v1/semantic_final

python -B -m scripts.DFG.dfg_v2.benchmark_v2.prepare_anon decision \
  --naming scripts/DFG/experiments/artifacts/dfg_v2/prompt8f_v1/naming \
  --semantic scripts/DFG/experiments/artifacts/dfg_v2/prompt8f_v1/semantic_final \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt8f_v1/acceptance

python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/dfg_v2/tests/test_prompt8f_anon_binding.py \
  scripts/DFG/dfg_v2/tests/test_prompt8f_anon_parity.py

python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
```

For the final full suites, the recorded commands additionally used dedicated
--basetemp locations under prompt8f_v1/_test_tmp. The parent must exist before
pytest starts. That disposable tree was deleted after both suites succeeded;
it contains no retained result. Commands and final test logs remain in the batch.

User-approved exceptions:
- Legacy function C constructors share contract C's anonymous name.
- Any file fallback blocks full-population probes/features/170-fit preparation.
  Do not drop sources or retain original features under the N-anon name.

Bindings are conservative, version-aware and limited to closed same-source
declarations/types. No compiler or full binding/type-system claim is made.
Unresolved overloads/overrides, assembly, version semantics or members produce
an identity fallback with no partial edit list. The shared reserved table is
frozen in naming/policy.json, along with the constructor/stop decisions.

Parity uses an in-memory code-only HCG copy. Metadata that binds the original
source SHA is never passed as compiler evidence for renamed text. Original
artifacts are read-only. Synthetic nodes without unique saved AST anchors may
only be rewritten when all exact AST-text candidates yield identical output;
otherwise their file cannot be a valid feature view.

Earlier semantic_parity and semantic_verified runs preserve development checker
findings. The final checker fixes a v2 audit-vocabulary collision and restores
declaration names only in known evidence fields. Exact source snapshots and SHA
receipts explain the revision; no historical seal is rewritten.

The blocked acceptance seal is not an execution plan. P2/P3 (including per-role
AUC), keyword baselines, new TokenEncoder vectors, identity/model assembly and
the 170-fit plan remain unexecuted. Complete them only after the binding and
projection blockers are resolved under an approved design. Existing 8D grouped
folds, labels and task matrix remain unchanged.

Final experiments are intended for a server with sufficient VRAM. Local 4GiB
limits are development constraints; server configuration and throughput have
not been measured, and local/server scores must not be mixed.
