#!/usr/bin/env bash
# Run a command in the pipeline image with the GPU, this checkout and a persistent cache.
#
#   docker/run.sh python -m dfg train --out runs/dfg/all
#   docker/run.sh bash                       # interactive shell
#
# MANDO_CACHE   host directory for model downloads, LLM cache and $HOME (default: ../mando-cache)
# MANDO_IMAGE   image tag (default: mando-llm:5080)
# Generated data (data/) and runs (runs/) stay in the checkout, owned by the calling user.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE="${MANDO_CACHE:-$(dirname "$REPO")/mando-cache}"
IMAGE="${MANDO_IMAGE:-mando-llm:5080}"
mkdir -p "$CACHE/home" "$CACHE/huggingface"
TTY=(-i)
[ -t 0 ] && [ -t 1 ] && TTY=(-it)
exec docker run --rm "${TTY[@]}" --gpus all --ipc=host \
    --user "$(id -u):$(id -g)" -e HOME=/cache/home \
    -v "$REPO":/work/repo -v "$CACHE":/cache -w /work/repo \
    "$IMAGE" "$@"
