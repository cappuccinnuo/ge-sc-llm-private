# dfg — data-flow augmentation of HCG graphs, and its training protocol

`dfg` takes the heterogeneous code graphs built by [`hcg`](../hcg/README.md)
(CFG + call graph, one node per statement) and adds data-flow structure, then trains
and compares HGT models with and without it.

| layer | relation(s) | what it adds |
|---|---|---|
| L1 | `DATA_DEF_USE` | statement → statement definition-use edges from per-function reaching definitions |
| L2 | `WRITES_STATE`, `READS_STATE` | statement ↔ state-variable access edges |
| L3 | `ENV_FLOW` | `env_source` nodes (`msg.sender`, `block.timestamp`, …) and their flow edges |

Every forward relation has a typed reverse (`REV_*`). A **profile** is the set of
relations a model registers: `G0` (plain HCG), `G1R` (L1 + reverse), `G2R`
(L1–L2 + reverse), `G3R` (L1–L3 + reverse), `G3` (L1–L3, forward only).

## Layout

```
dfg/
  schema.py        relation vocabulary and profiles
  analysis/        source-level analysis of Solidity (tree-sitter), no graph knowledge
    frontend.py    source views, compiler-version interval
    ir.py          data-flow IR
    symbols.py     symbol tables, static call binding
    access.py      variable read/write extraction
    cfg.py         statement-level semantic CFG
    dataflow.py    reaching definitions
    state.py       state binding, modifiers, coverage-extended CFG
    units.py       statement regions
  graph/           augmentation of an HCG
    projection.py  facts -> HCG nodes (exact AST anchoring, refuses ambiguity)
    local.py       L1
    binding.py     state-variable binding shared by L2/L3
    state.py       L2
    env.py         L3
    pipeline.py    cumulative L1 -> L2 -> L3 with invariant checks
    audit.py       content fingerprints
  model/           HGT over augmented graphs (DGL)
  inputs.py        hcg outputs -> task inputs (sources, recorded compiler versions, tokens)
  store.py         writes the augmented graph store
  train/           grouped nested cross-validation (see below)
  __main__.py      CLI
```

Each layer imports only from the layers above it in this list.

## Usage

```bash
python -m hcg fetch                 # pinned SmartBugs-curated + SolidiFI checkouts
python -m hcg build                 # data/hcg/A/<category>/ (with CodeT5+ tokens)
python -m dfg build                 # data/dfg/A/<category>/<task>/F1..F3
python -m dfg train --out runs/dfg/all --device cuda:0
python -m dfg report runs/dfg/all
```

Narrower runs: `--categories reentrancy access_control`, `--tasks node`,
`--profiles G0 G3R`, `--folds 0 1`, `--epochs 2` (smoke). `train` skips fits whose
`result.json` exists, so an interrupted run resumes. `data/` and `runs/` are not
tracked by git.

Tasks: `<category>_contract` (all contracts, contract labels) and `<category>_node`
(vulnerable contracts, node labels), from hcg's `contract_level` and `line_level`.

## Training protocol (`dfg.train`)

The numerics of the Prompt 8H benchmark, without its sealing layer:


* **Folds** (`splits.py`): source files are grouped by duplicates (exact after removing
  whitespace; near = comments also removed, `SequenceMatcher` ratio ≥ 0.98), then groups
  are assigned to 5 (contract) or 10 (node) outer folds and each remainder to inner
  train/validation 80/20 by deterministic greedy stratification (file class × SolidiFI
  cohort, node label counts). Duplicates never straddle train and test.
* **Features**: by default the HCG node tokens of the original code (the project's
  main view, shared with NodeSem/EdgeSem). `--features anonymous` (`features.py`)
  recomputes them after a per-file bijective renaming of user identifiers
  (`bug_txorigin20` → `v17`), the Prompt 8H view, since SolidiFI's injected names can
  leak labels. Builtins, globals and keywords are kept; files the grammar cannot parse
  keep their original tokens and are listed in `task.json`. Scores of the two views are
  not paired with each other.
* **Initialization** (`init.py`): per fold a G0 model is built with the fold's
  constructor seed; every other profile copies G0's parameters by semantic identity and
  draws only its new relation/node rows. Profiles differ in structure, not initial weights.
* **Fit** (`trainer.py`): full-batch Adam + OneCycle (one step per epoch), cross-entropy,
  at most 50 epochs (OneCycle div factor 20 for contract, 25 for node tasks); the best checkpoint is the minimum inner-validation loss (patience 7,
  δ 0.001). Outer-test labels are read only after fitting. `env_source` nodes are never
  supervised or scored. Contract: lr 5e-4 → 1e-2, weight decay 5e-6; node: lr 2e-4 →
  5e-3, no weight decay; hidden 128, 2 layers, 8 heads, shared-projection HGT layer.
* **Report** (`report.py`): fold means (SD) of outer-test scores; each profile vs G0 fold
  by fold (Wilcoxon zsplit + Holm for node tasks; contract tasks descriptive); the
  selected profile G* uses inner validation only.

Labels are hcg's (the Oct 10 public-annotation policy). The Prompt 8 diagnostic
relabeling ("L-audit") and the G0P placebo are not part of this package; they remain
on the archive branch `archive/pre-restructure-2026-11-15`.

## Verification

`tests/dfg/` checks the package against two independent references:

* **Pre-restructure code**: content fingerprints of every layer (F0–F3) for all
  7 categories × 2 tasks, computed by the old `scripts/DFG` code from the same HCG graphs
  (`reference/fingerprints.json`).
* **Sealed Prompt 8 evidence** (reentrancy, access control; built from the authors'
  graphs): per-profile canonical relation edge counts, fold-0 initial parameter digests of
  every profile, the anonymized code of every node, the 30 nested folds (from the sealed
  population rows) and the duplicate-group partitions.

`test_dataset_a.py` needs `$MANDO_DATA_DIR` (`python -m hcg fetch`) and takes a few
minutes per category (`-k <category>`); CI runs it for every category.

## Where things came from

The code was moved from `scripts/DFG` (v1 analyzers, state stages F/J/K, `dfg_v2`,
`benchmark_v2`). Modules that only served sealed audits, provenance gates or superseded
experiments were dropped. `scripts/DFG/__init__.py` maps the old module names of moved
code onto this package for NodeSem/EdgeSem until those are integrated.
