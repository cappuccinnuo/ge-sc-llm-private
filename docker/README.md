# Running the pipeline on the RTX 5080 (WSL2 + Docker)

The GPU environment is one image, built from NVIDIA's DGL 25.08 container (Ubuntu 24.04,
CUDA 13.0, PyTorch 2.8, DGL 2.5, Python 3.12) plus `requirements.txt` and llama.cpp built
for the 5080 (sm_120). The checkout is mounted into the container, so code updates need
only `git pull`; the image is rebuilt only when `requirements.txt` or the Dockerfile change.

| File | Purpose |
|---|---|
| `Dockerfile` | the image (`mando-llm:5080`) |
| `run.sh` | run any command in the image with the GPU, the checkout and the cache mounted |
| `check_env.py` | environment check: GPU, PyTorch for sm_120, DGL GPU kernels, grammar, llama.cpp |
| `smoke.sh` | the whole pipeline on one category (fold 0, 2 epochs) after the equivalence tests |

## 1. Prerequisites (once)

* **Windows NVIDIA driver** recent enough for CUDA 13: in WSL, `nvidia-smi` must show the
  RTX 5080 and `CUDA Version: 13.0` or higher. Update the driver on Windows if not.
  Do not install a Linux NVIDIA driver inside WSL; WSL uses the Windows one.
* **Docker with GPU support**, either Docker Desktop (Settings → Resources → WSL
  integration on for your Ubuntu distribution) or Docker Engine installed in WSL plus the
  NVIDIA Container Toolkit. Check with
  `docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu24.04 nvidia-smi -L`.
* **Disk**: put the checkout on the WSL filesystem (e.g. `~/work`), not under `/mnt/c`,
  which is many times slower. Plan for about 100 GB: image ~25 GB, models ~3 GB, data
  and runs the rest.
* **Memory**: WSL gets half of the Windows RAM by default; raise it in
  `%UserProfile%\.wslconfig` (`[wsl2]` `memory=...`) if builds are killed.

## 2. Code and image

```bash
mkdir -p ~/work && cd ~/work
git clone -b rtx5080-rebuild git@github.com:cappuccinnuo/ge-sc-llm-private.git
cd ge-sc-llm-private
docker build -f docker/Dockerfile -t mando-llm:5080 .      # 20-40 min, mostly llama.cpp
```

`docker/run.sh` keeps the Hugging Face model downloads (CodeT5+, BGE, the Qwen GGUF)
and `$HOME` in `~/work/mando-cache` (set `MANDO_CACHE` to move it) and runs as your user,
so everything written to `data/` (including the LLM response cache) and `runs/` stays
yours.

## 3. Check and smoke run

```bash
docker/run.sh python docker/check_env.py          # seconds
docker/run.sh docker/smoke.sh                     # access_control; ~1-2 h with the dataset tests
```

`smoke.sh` stops at the first failure and writes `runs/smoke/smoke_access_control.log`
with the time of every step; that log is what to send back. `SKIP_DATASET_TESTS=1`
skips the equivalence tests (only after they have passed once on this machine).

What a failed check means:

| Check | Likely cause |
|---|---|
| GPU | driver too old for CUDA 13, or Docker started without GPU support |
| PyTorch built for … not sm_120 | the base image lacks Blackwell kernels: a different base image is needed |
| DGL GPU kernels | the container's DGL was not built for sm_120: DGL must be built from source |
| tree-sitter grammar | no C compiler or setuptools in the image |
| llama.cpp | llama-cpp-python was built without CUDA; check the `docker build` log |

## 4. Full run

Run long jobs inside `tmux` (they resume if interrupted). In order:

```bash
docker/run.sh python -m hcg fetch
docker/run.sh python -m hcg build
docker/run.sh python -m dfg build
docker/run.sh python -m dfg train --out runs/dfg/all
docker/run.sh python -m nodesem analyze
docker/run.sh python -m nodesem encode
docker/run.sh python -m nodesem describe          # the longest step (LLM, all 7 categories)
docker/run.sh python -m nodesem encode --teacher
docker/run.sh python -m nodesem train --out runs/nodesem/all
docker/run.sh python -m edgesem build
docker/run.sh python -m edgesem train --out runs/edgesem/all
```

`dfg train`, `nodesem train` and `edgesem train` print a paired report at the end (also
`python -m <stage> report <run dir>`). The `dfg`, `nodesem` and `edgesem` trainings are
independent of each other once their inputs exist.
