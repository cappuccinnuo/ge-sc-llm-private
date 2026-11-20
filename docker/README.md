# Running the pipeline on the RTX 5080 (WSL2 + Docker)

The GPU environment is one image, built from an NVIDIA DGL container (default 25.05:
CUDA 12.9, DGL 2.5, Python 3.12; `--build-arg BASE=nvcr.io/nvidia/dgl:25.08-py3` for
CUDA 13.0) plus `requirements.txt` and llama.cpp built for the 5080 (sm_120). The checkout is mounted into the container, so code updates need
only `git pull`; the image is rebuilt only when `requirements.txt` or the Dockerfile change.

| File | Purpose |
|---|---|
| `Dockerfile` | the image (`mando-llm:5080`) |
| `run.sh` | run any command in the image with the GPU, the checkout and the cache mounted |
| `check_env.py` | environment check: GPU, PyTorch for sm_120, DGL GPU kernels, grammar, llama.cpp |
| `smoke.sh` | the whole pipeline on one category (fold 0, 2 epochs) after the equivalence tests |
| `benchmark.sh` | the MANDO-LLM baseline from source to final detection on all 7 categories, against the paper |

## 1. Prerequisites (once)

* **Windows NVIDIA driver** recent enough for the base image's CUDA: in WSL, `nvidia-smi`
  must show the RTX 5080 and a CUDA version at least that of the image (12.9 for 25.05,
  13.0 for 25.08). Update the driver on Windows if not.
  Do not install a Linux NVIDIA driver inside WSL; WSL uses the Windows one.
* **Docker with GPU support**, either Docker Desktop (Settings → Resources → WSL
  integration on for your Ubuntu distribution) or Docker Engine installed in WSL plus the
  NVIDIA Container Toolkit. Check with the base image itself (it must list the GPU):
  `docker run --rm --gpus all nvcr.io/nvidia/dgl:25.05-py3 nvidia-smi -L`.
* **Docker without sudo**: `docker/run.sh` runs containers as your user so `data/` and
  `runs/` stay yours; with `sudo` they would belong to root. Once:
  `sudo usermod -aG docker $USER`, then `wsl --shutdown` in Windows and reopen WSL.
* **Disk**: put the checkout on the WSL filesystem (e.g. `~/work`), not under `/mnt/c`,
  which is many times slower. Plan for about 150 GB: image ~50 GB, models ~3 GB, data
  and runs the rest.
* **Memory**: WSL gets half of the Windows RAM by default; raise it in
  `%UserProfile%\.wslconfig` (`[wsl2]` `memory=...`) if builds are killed.

* **Network**: the pipeline downloads the two label repositories from GitHub
  (`hcg fetch`) and the encoder/LLM weights from Hugging Face. `docker/run.sh` gives the
  container the host's network, its `http(s)_proxy`/`no_proxy`/`HF_ENDPOINT` variables
  and `~/.gitconfig` (read-only), so whatever works in the WSL shell works inside. Check
  from the shell first:
  `git ls-remote https://github.com/smartbugs/smartbugs-curated.git HEAD` and
  `curl -sI https://huggingface.co | head -1`. Behind a proxy, export it in the shell
  (e.g. `export https_proxy=http://<host>:<port> http_proxy=$https_proxy`) before
  `docker/run.sh`; the proxy must be reachable from WSL (with WSL's default NAT
  networking that is the Windows host's address, not 127.0.0.1).
* **Model downloads**: `python -m hcg fetch` also downloads the four pinned models and
  verifies every file (size, ETag and content hash against the Hub's listing at the
  pinned commit) before it enters the cache; nothing unverified is ever cached, and
  broken cache entries (such as 0-byte `config.json` files from an earlier download)
  are replaced while verified weights are kept. Some proxies answer `HEAD` with
  `Content-Length: 0`; the downloader never relies on that value.
  `docker/run.sh python -m hcg fetch --diagnose-hub` prints what `HEAD`, a 1-byte Range
  `GET` and a full `GET` return through the configured proxy and directly, with
  `Via`/`Server`/cache headers, to identify which layer rewrites the length.

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

## 4. Benchmark: source to detection, against the paper

```bash
QUICK=1 docker/run.sh docker/benchmark.sh     # plumbing: reentrancy, fold 0, 2 epochs (minutes)
docker/run.sh docker/benchmark.sh             # all 7 categories, 4-10 h; run inside tmux
```

It rebuilds the graphs of every category from the Solidity sources (`hcg build` into
`runs/benchmark/full/hcg`, checked against the paper's Table 1 and the authors' graphs),
then trains and scores the MANDO-LLM baseline (G0) under the paper's protocol and the
grouped protocol, with the authors' own trainers as a cross-check (55 fits per
category). The result is `runs/benchmark/full/report.md` (contract level vs. paper
Table 3, line level vs. Table 5, source-line scores, the two-phase detector) with
`evaluation.json`, `findings/` and `benchmark.log`. Rerunning the same command resumes
an interrupted run. To return the results, commit `report.md`, `evaluation.json`,
`run.json`, `benchmark.log` and `findings/` of `runs/benchmark/full/` (not the per-fold
files or `hcg/`, which are large). Details: [`benchmark/README.md`](../benchmark/README.md).

### Dataset B graphs

```bash
docker/run.sh python -m hcg fetch --dataset B --no-models   # the authors' DAppSCAN release, clean pool
docker/run.sh python -m hcg build --dataset B               # data/hcg/B/<category>, with tokens (~10 min)
```

The composition is fixed in `hcg/datasets/dataset_b.json` (see `hcg/README.md`, Dataset B).
The benchmark on Dataset B, against the paper's Tables 4 and 6, builds its own graphs:

```bash
QUICK=1 DATASET=B docker/run.sh docker/benchmark.sh   # plumbing: reentrancy, fold 0, 2 epochs
DATASET=B docker/run.sh docker/benchmark.sh           # all 7 categories -> runs/benchmark/full_b
```

## 5. Full run of the enhancements

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
