# MANDO-LLM with data-flow and semantic enhancements

Smart-contract vulnerability detection with heterogeneous graph transformers (HGT),
extending [MANDO-LLM](https://github.com/MANDO-Project/ge-sc-llm). Every stage is rebuilt
from the raw Solidity sources, so all graphs, features and model weights can be
regenerated on a new machine. Each stage reads only the outputs of the stages before it,
and refuses outputs that were built from different inputs.

```
Solidity sources ──► hcg ──► dfg ──► nodesem ──► (training)
                      │       │  └──► edgesem ──► (training)
                      │       └──► dfg train  (DFG profiles; G0 = MANDO-LLM baseline)
                      └──► mando classifiers (upstream baseline on the rebuilt graphs)
```

| Stage | What it adds | Output |
|---|---|---|
| [`hcg`](hcg/README.md) | contract graphs (CFG + call graph) in the authors' format, labels, CodeT5+ tokens; checked against the authors' released graphs | `data/hcg/` |
| [`dfg`](dfg/README.md) | data-flow layers L1 def-use, L2 state reads/writes, L3 environment flow; grouped nested CV training | `data/dfg/`, `runs/dfg/` |
| [`nodesem`](nodesem/README.md) | node semantics: code/context encoders, static facts, LLM descriptions (Qwen2.5-Coder) distilled into a student | `data/nodesem/`, `runs/nodesem/` |
| [`edgesem`](edgesem/README.md) | edge semantics: MOD_APPLY / CALL_SITE / GUARDS relations, 74-bit edge attributes, edge-aware HGT | `data/edgesem/`, `runs/edgesem/` |
| [`mando`](mando/README.md) | the upstream MANDO-LLM baseline: HGT models, tree-sitter graph construction, trainers, inference | — |

## Layout

```
hcg/ dfg/ nodesem/ edgesem/   pipeline stages (each: README, CLI `python -m <stage>`, layered subpackages)
mando/                        upstream MANDO-LLM baseline (models/, graphs/, classifiers, inference)
compile_repair/               compile-repair subsystem (in development)
tests/                        per-package tests: hcg/ dfg/ nodesem/ edgesem/ mando/ (+ reference data)
data/upstream_mando_llm/      the authors' released graphs (reference for hcg)
experiments/ge-sc-data/       Dataset A Solidity sources
docker/                       GPU image, environment check and smoke run (RTX 5080 / WSL2)
docs/                         migration_5080.md (rebuild log), history/ (earlier handovers and archives)
.github/workflows/            CI: unit tests + every category end to end on CPU
```

Generated data goes to `data/` and training runs to `runs/` (both git-ignored).

## Setup

* **GPU (RTX 5080, WSL2):** one Docker image based on NVIDIA's DGL 25.08 container
  (CUDA 13.0, PyTorch 2.8, DGL 2.5, Python 3.12); see [`docker/README.md`](docker/README.md)
  for prerequisites, the environment check, the smoke run and the full run.
* **CPU (as in CI):** Python 3.11 with `torch==2.2.1` (CPU wheel), `dgl==2.1.0` and
  `numpy<2`, then `pip install -r requirements.txt` (plus llama-cpp-python for
  `nodesem describe`, see the end of `requirements.txt`).

`requirements.txt` holds every pin on top of PyTorch + DGL for both. A C compiler is
needed once to build the tree-sitter grammar.

## Running everything

```bash
python -m hcg fetch                       # pinned SmartBugs-curated + SolidiFI (data/ or $MANDO_DATA_DIR)
python -m hcg build                       # 7 categories, with tokens
python -m dfg build
python -m dfg train --out runs/dfg/all && python -m dfg report runs/dfg/all

python -m nodesem analyze && python -m nodesem encode
python -m nodesem describe && python -m nodesem encode --teacher
python -m nodesem train --out runs/nodesem/all && python -m nodesem report runs/nodesem/all

python -m edgesem build
python -m edgesem train --out runs/edgesem/all && python -m edgesem report runs/edgesem/all
```

Training commands use the GPU when available (`--device`), resume interrupted runs and
accept `--categories`, `--tasks`, `--folds` and `--seed`; the stage READMEs list the
rest. The upstream baseline runs as `python -m mando.graph_classifier` /
`python -m mando.node_classifier` (see `mando/README.md`).

## Verification

`python -m pytest tests/<stage>/test_units.py` runs without data. The
`tests/<stage>/test_dataset_a.py` suites (need `$MANDO_DATA_DIR`) rebuild each category
and check it against the authors' graphs, the pre-restructure code and the sealed
evidence of the earlier experiments; CI runs them for all seven categories.

Code and artifacts removed during the restructure are kept on the branches
`archive/pre-restructure-2026-11-15` and `archive/pre-root-tidy-2026-11-16`.
