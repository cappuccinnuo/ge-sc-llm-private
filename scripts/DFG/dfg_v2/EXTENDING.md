# Extending DFG v2 to another vulnerability category

This procedure changes registration and frozen input artifacts only. L1/L2/L3
analysis, graph projection, relation definitions, tokenizer and HGT do not need
category-specific branches. Currently only `reentrancy` and `access_control`
are registered; the other five Dataset A categories remain a comment.

Public task names are `<category>_contract` and `<category>_node`.
Historical `source_task_id` remains separate provenance. Original node labels
and the complete 512-dimensional `inside_token` feature record are preserved.
These features were locally encoded from author graphs, not author-supplied
vectors.

## 1. Prepare the category registration

Add one category record matching `tasks.REGISTRY`. Each granularity needs
pinned `{path, sha256}` references:

- `source_task_manifest`: includes original `graphs.HCG` and `feature`.
- `source_metadata_manifest`: file-to-path/SHA/recorded version metadata.
- `prepared_manifest`: original preparation identity.
- `labels`: unique `contract_name` and binary integer `targets`.
- `folds`: nested document prepared in step 3.

Keep task/cohort identities and source-task labels/prepared references
consistent. Do not infer paths by renaming another category.

The separate source metadata reference fills a real historical interface gap:
the task document does not embed the later verified version metadata. It
preserves accepted SupportedSourceView behavior and never guesses a compiler.

The contract graph contains both classes; the node graph contains only the
fixed buggy-file population. A source absent from its mapping causes explicit
per-file fallback without deleting its graph. A registered source disappearing
or changing SHA is an input error. Referenced version CSV/origin sources are
also verified.

## 2. Repeat the relevant Prompt 0 checks

Check source identity, declaration anchors/projection, original labels, token
equality and tokenizer asset hashes for the new category. Preserve evidence.
The existing four-task audit does not magically gain an unsupported
`--category` flag: use the checked APIs with a newly audited category manifest.
Do not transfer R/AC acceptance to new files.

## 3. Bootstrap and seal the first folds, then verify registration

The strict registry requires existing pinned fold files. Bootstrap new files
with the original protocol function first. `tasks.make_folds` regenerates and
compares an existing document in memory; it does not create or overwrite it.

```python
from pathlib import Path
from scripts.DFG.experiments.protocol import make_fold_document
from scripts.DFG.integration.io import sha256, write_json

# file_labels: exactly the original task graph's filenames.
# node task: only files with graph label 1.
document = make_fold_document(
    file_labels, task, prepared_manifest_sha256,
    seed=1, inner_fraction=0.2,
)
# Choose a NEW folds_path and enforce no overwrite.
folds_path = Path(folds_path)
if folds_path.exists():
    raise FileExistsError(str(folds_path))
write_json(folds_path, document)
fold_ref = {"path": str(folds_path), "sha256": sha256(folds_path)}
```

Register fold_ref. The document contains its own `split_sha256` and the input
manifest subsequently seals the reference. Use the ORIGINAL prepared-manifest
SHA, not the new DFG v2 input-manifest SHA.

Retain 5 contract / 10 node outer folds and frozen inner validation. Contract
splitting needs at least five files per class and sufficient examples for both
classes in each inner partition. Node splitting needs at least ten buggy files.
The interface test uses 20 synthetic identities (10 clean / 10 buggy), keeping
both existing protocols unchanged.

```python
from scripts.DFG.dfg_v2.tasks import make_folds
documents = make_folds("new_category")  # after registering pinned refs
```

These are locally frozen nested folds, not author-published splits. Do not
change them after inspecting scores.

## 4. Seal inputs and build/verify a new graph store

Run from the repository root in the existing mando environment, using the same
local Tree-sitter grammar configuration as other v2 commands.

```python
from scripts.DFG.dfg_v2.inputs import build_manifest
path = build_manifest(
    "scripts/DFG/experiments/artifacts/dfg_v2/inputs_new_category",
    task_ids=["new_category_contract", "new_category_node"],
)
```

Existing output directories are rejected. This writes `manifest.json` and
`manifest.seal.json` with original HCG, exact sources, labels, nested folds,
complete feature provenance and local tokenizer assets.

```bash
python -B -m scripts.DFG.dfg_v2.cli build \
  --manifest scripts/DFG/experiments/artifacts/dfg_v2/inputs_new_category/manifest.json \
  --tasks new_category_contract,new_category_node \
  --graph-keys F1,F2,F3 \
  --output scripts/DFG/experiments/artifacts/dfg_v2/graphs_new_category

python -B -m scripts.DFG.dfg_v2.cli verify \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_new_category/store.json
```

F0 references original graph bytes. F1/F2/F3 reuse the preceding layer's output,
calling each augmenter once per task. Source text is loaded once per task, but
the frozen augmenters retain independent AST parsing.

Store verification binds inputs, graph bytes and audits without requiring
current runtime to equal build-time runtime. Unrelated later commits are
allowed; graph/input drift is not.

## 5. Plan the selected-profile experiment after Prompt 7 exists

The experiment runner belongs to Prompt 7 and is NOT implemented by Prompt 5.
Do not claim or run `run plan` until its training-equivalence/checkpoint tests
pass. When available, compare previously selected R/AC profile G* with G0 on the
sealed store and frozen nested folds. Do not reselect G* using new-category
outer-test scores. Graph building does not authorize additional training.

## Public APIs and verification boundaries

- `get_tasks(task_ids=None, registry=None)` returns task-ID-to-bound-record;
  category names expand both granularities. Unknown/repeated tasks are rejected.
- `make_folds(category, registry=None)` verifies regenerated frozen documents.
- `build_manifest(output, task_ids=None, registry=None)` returns a new manifest path.
- `load_manifest(path, check_files=True)` always checks seal and schema;
  false is binding-only inspection, not asset verification.
- `load_task(record)` verifies assets and returns original graph, source texts
  and version metadata.

The complete synthetic integration test is `tests/test_tasks.py`. Its fixture
encoder and small model dimensions are test-only, not formal data/results.
No Solidity compilation is claimed by parser-backed tests.
