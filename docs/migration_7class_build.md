# Seven-category build from raw .sol, and moving to the RTX 5080 machine

Branch `migrate-7class-build` (from `edge-sem` @ 88cc13a7), 2026-11-15.

## Ground rule: no existing file is modified

Sealed DFG / node-sem / edge-sem manifests pin the SHA-256 of the existing build and
model code (for example `scripts/encode_tokenizer_features.py` in 426 files,
`sco_models/model_hgt.py` in 410), and `scripts/edge_sem/hgt_edge.py` refuses to
import if `sco_models/model_hgt.py` changes. So this branch only **adds** files.
CI fails if anything outside that set changes. Where an existing script cannot run
on the new machine as it stands, the new code reuses its pure helper functions
unchanged and re-expresses only the surrounding loop.

## What a fresh clone could not do, and what now does it

| Gap | Fix (new files only) |
|---|---|
| `process_graphs/tree_sitter_codeviews/build/my-languages.so` in git is a **macOS arm64** binary; the Linux grammar lived in the ignored `build/linux-x86_64/`, so no `.sol` parsed (two existing tests failed on a fresh Linux clone too) | `TREE_SITTER_LIB_DIR` defaults to `<repo>/build/<platform>-<machine>` (git-ignored, the old machine's convention); `custom_parser` compiles the vendored grammar there on first use (needs gcc). Set by `scripts/graph_build`, `tests/conftest.py`, the Dockerfile and CI |
| build scripts default to reentrancy, call `nx.write_gpickle` (removed in networkx 3) and have no multi-category driver | `python -m scripts.graph_build` builds any or all of the 7; pickle I/O in `scripts/graph_build/nx_io.py` (protocol 4, readable by the old Python 3.7 env) |
| label sources cloned into `/home/zhao/...`, unpinned | `scripts/graph_build/fetch_labels.sh`: `$MANDO_DATA_DIR` or `<repo>/data`, pinned commits, idempotent |
| `train_*level.sh` hard-code `/home/zhao`, conda, and reentrancy | `scripts/train_all_categories.sh`: same classifier arguments, any categories |
| `model_hgt.py` imports `torch_geometric` at load time | installed as the pure-Python wheel (`docker/requirements.txt`); no torch-scatter / CUDA extension builds |
| no environment for Blackwell (sm_120) | `docker/Dockerfile` on NVIDIA's DGL 25.08 container + `docker/requirements.txt` |

Training itself needed no change: `graph_classifier.py` / `node_classifier.py` read
graphs through `sco_models.graph_utils.read_gpickle`, which already falls back to
pickle on networkx 3, and checkpoints are plain `state_dict`s, so torch >= 2.6's
`weights_only=True` default does not affect them.

## Running it

```bash
bash scripts/graph_build/fetch_labels.sh           # SmartBugs + SolidiFI, pinned
python -m scripts.graph_build --check              # all 7; --no_tokens skips HF
bash scripts/train_all_categories.sh inside_token  # contract + line level, all 7
bash scripts/train_all_categories.sh nodetype      # structure-only baseline
```

`train_all_categories.sh [feature] [category ...]`; `PHASES=contract` or
`PHASES=line` runs one phase; `NUM_EPOCHS`, `K_FOLDS`, `SEED` override the paper
settings. Models: `models/<level>/<tag>/<category>_hgt.pth` (the old layout);
logs: `logs/<level>_<tag>/<category>/`.

On the RTX 5080 machine (Linux, or WSL2 on Windows; driver >= 570 and the NVIDIA
Container Toolkit):

```bash
docker build -t mando-llm:5080 -f docker/Dockerfile docker
docker run --gpus all --rm -it --shm-size 8g \
  -v "$PWD":/workspace/ge-sc-llm -v "$HOME/.cache/huggingface":/root/.cache/huggingface \
  mando-llm:5080
# inside: python -m pytest -q tests, then the commands above
```

## Category to label-source mapping

Established by hashing every `buggy_N.sol` in each corpus against the SolidiFI
benchmark; every file matched exactly one folder. The names do not line up
obviously, so the registry (`scripts/graph_build/categories.py`) records them:

| Category | SolidiFI folder | Contracts (buggy : clean) |
|---|---|---|
| access_control | tx.origin | 114 (57 : 57) |
| arithmetic | Overflow-Underflow | 120 (60 : 60) |
| denial_of_service | Unhandled-Exceptions | 92 (46 : 46) |
| front_running | TOD | 88 (44 : 44) |
| reentrancy | Re-entrancy | 142 (71 : 71) |
| time_manipulation | Timestamp-Dependency | 100 (50 : 50) |
| unchecked_low_level_calls | Unchecked-Send | 190 (95 : 95) |

The other buggy files are labelled by SmartBugs curated `vulnerabilities.json`; the
clean half has no annotation. As upstream, no category filter is applied.

## Verification

Full build, Python 3.11 / networkx 3.6 / freshly compiled grammar:

| Category | Nodes | Edges | Buggy nodes | Line-level nodes |
|---|---|---|---|---|
| access_control | 13432 | 15538 | 3236 | 7710 |
| arithmetic | 16157 | 17591 | 5881 | 10469 |
| denial_of_service | 12909 | 14366 | 4238 | 8364 |
| front_running | 19415 | 22278 | 11001 | 15138 |
| reentrancy | 18312 | 19267 | 6978 | 12036 |
| time_manipulation | 15699 | 18564 | 6151 | 10639 |
| unchecked_low_level_calls | 17525 | 20952 | 2714 | 9332 |

- Contracts, buggy contracts, nodes and edges equal the paper's Table 1 for **all
  seven** categories (`Test_code/author_graph_audit/audit_author_graphs.py::PAPER`);
  `--check` enforces it.
- Reentrancy reproduces the documented earlier rebuild exactly (6978 buggy nodes,
  12036 line-level nodes) and rewrites the tracked `graph_labels.json` byte-identical.
- Buggy-node counts exceed the paper's in every category: the known labelling-width
  difference (HANDOVER.md section 4). The other six buggy-node and line-level counts
  are this build's own baseline, a regression lock rather than ground truth.
- Training smoke (1 epoch x 2 folds, CPU, both phases, `nodetype` and
  `inside_token`) on unmodified `sco_models/`: torch 2.2 / DGL 2.1 locally, torch
  2.4 / DGL 2.4 in CI.
- CI (`.github/workflows/graph-build-7class.yml`, sparse ~80 MB checkout since the
  full tree is ~14 GB): unit tests, the
  no-existing-file-changed check, then per category: fetch labels, build with the
  real CodeT5+ tokenizer, `--check`, both smoke trainings.

## Not covered

- **The Docker image was not built or run**: the build workspace cannot reach
  `nvcr.io` and has no GPU, and the image is too large for a GitHub runner. First
  thing on the new machine: build it, check the printed torch / CUDA / DGL line, run
  the tests.
- GPU numerics differ from the RTX 3050 / CUDA 11.1 runs; rerun baselines and
  innovations on the new machine rather than mixing machines in one table.
- These graphs come from the local generator. DFG v2, node-sem and edge-sem consume
  the authors' graphs and are registered for reentrancy / access_control only;
  running them on these seven builds is separate work.
- The old scripts (`scripts/train_*level.sh`, `fetch_vuln_labels.sh`,
  `make_linelevel_graphs.sh`, ~120 audit scripts) still hard-code `/home/zhao` and
  are left as sealed history.

## Change log (all new files)

- `scripts/graph_build/categories.py`: registry, SolidiFI mapping, paper and baseline counts.
- `scripts/graph_build/pipeline.py`: stages 1-5, grammar location, `check_expected`.
- `scripts/graph_build/__main__.py`: CLI.
- `scripts/graph_build/nx_io.py`: networkx-version-independent gpickle I/O.
- `scripts/graph_build/fetch_labels.sh`: pinned label sources.
- `scripts/train_all_categories.sh`: both phases over any set of categories.
- `docker/Dockerfile`, `docker/requirements.txt`.
- `tests/test_graph_build.py`: synthetic end-to-end build, registry, label sources,
  grammar location, edge_sem frozen sources.
- `tests/conftest.py`: per-platform grammar default for the test suite.
- `.github/workflows/graph-build-7class.yml`.
