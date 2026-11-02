# NS-P2 offline M1 encoder

This directory runs in **nodesem (Python 3.10)**. The graph pipeline remains in
**mando (Python 3.7)**. Neither environment imports the other's runtime modules;
text JSONL, float32 NPZ, and SHA-bound manifests are the interface.

The current user explicitly authorized creating nodesem and downloading its
dependencies, overriding PROMPTS section 5.4's original user-preparation requirement.
The environment is on the E-backed WSL disk. Do not install these packages in
mando. User-site packages must be disabled; the encoder refuses otherwise.

## Local assets

`assets.json` records all files and revisions of the three official snapshots
under `Pre-trained-model/`. Model loading is local-only, including the CodeT5
custom Python implementation, and rechecks every asset SHA before loading.
CodeT5 and UniXcoder weights are `pytorch_model.bin`; BGE uses
`model.safetensors`. Weights are not committed to Git.

The main CodeT5 model emits a **256-dimensional normalized** vector: its own
forward calls `F.normalize` after the projection. The encoder does not normalize
it a second time. GPU inference uses fp16, saved vectors use float32.
UniXcoder's optional 768-dimensional masked mean path has unit tests; this phase
does not run its full-data alternative or BGE teacher inference.

## Reproduce after restoring referenced inputs

In mando, from the project root:

```bash
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
CUDA_VISIBLE_DEVICES='' python -B -m scripts.node_sem.p2_acceptance texts \
  --texts-root scripts/node_sem/artifacts/text_v1 \
  --audit scripts/node_sem/artifacts/ns_p2
```

In nodesem, run one task/view at a time:

```bash
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
python -s -B scripts/node_sem/offline/encode.py \
  --texts scripts/node_sem/artifacts/text_v1/anonymous/reentrancy_node/text.jsonl \
  --model codet5p-110m-embedding --max-length 128 --pooling model_default \
  --batch-size 32 --device cuda \
  --out scripts/node_sem/artifacts/ns_p2/encoded/anonymous/reentrancy_node
```

Repeat for original/anonymous and the four tasks listed in
`artifacts/ns_p2/encoding_plan.json`. Each invocation does two independent forward
passes with the same sorted batches; it fails above maximum absolute difference
1e-6. No optimizer is created. A held DFG training lock rejects GPU execution.
Failures preserve their directory; no automatic retries or CPU fallback.

Back in mando:

```bash
CUDA_VISIBLE_DEVICES='' python -B -m scripts.node_sem.p2_acceptance verify
```

All output directories are exclusive. To repeat, choose **new** text, encoded,
and audit directories and pass their paths explicitly. Never overwrite a sealed
batch. Changes to the producer or its bound dependencies require new features.

## Validation

```bash
# nodesem only; this file is deliberately outside default test_*.py discovery
CUDA_VISIBLE_DEVICES='' python -s -B -m pytest -q -p no:cacheprovider \
  scripts/node_sem/tests/offline_checks.py

# mando: the three suites mandated by shared context
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
```

`requirements-nodesem-lock.txt` pins the verified Linux x86_64/Python 3.10 wheels
and their SHA256 values (torch 2.6.0+cu118, transformers 4.46.3). CUDA 11.8 was
chosen for the existing local driver; no driver or mando upgrade was made.
The installation and environment checks are recorded in `artifacts/ns_p2/environment/`.

Final model experiments are intended for a server with sufficient VRAM.
The 4 GiB GPU is a local development constraint; no server deployment is claimed.
NS-P2 only supplies M1 features and registers S2. It does not implement the
NS-P4 concat adapter or report detection improvements.
