#!/usr/bin/env bash
# Run a command in the pipeline image with the GPU, this checkout and a persistent cache.
#
#   docker/run.sh python -m dfg train --out runs/dfg/all
#   docker/run.sh bash                       # interactive shell
#
# MANDO_CACHE   host directory for model downloads and $HOME (default: ../mando-cache)
# MANDO_IMAGE   image tag (default: mando-llm:5080)
# Generated data (data/) and runs (runs/) stay in the checkout, owned by the calling user.
# The container uses the host's network, proxy variables and ~/.gitconfig (read-only), so
# GitHub and Hugging Face are reached exactly as from the host shell.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE="${MANDO_CACHE:-$(dirname "$REPO")/mando-cache}"
IMAGE="${MANDO_IMAGE:-mando-llm:5080}"
mkdir -p "$CACHE/home" "$CACHE/huggingface"
TTY=(-i)
[ -t 0 ] && [ -t 1 ] && TTY=(-it)
PASS=()
for name in http_proxy https_proxy no_proxy all_proxy HTTP_PROXY HTTPS_PROXY NO_PROXY ALL_PROXY HF_ENDPOINT; do
    [ -n "${!name:-}" ] && PASS+=(-e "$name")
done
[ -f "$HOME/.gitconfig" ] && PASS+=(-v "$HOME/.gitconfig:/cache/home/.gitconfig:ro")
exec docker run --rm "${TTY[@]}" --gpus all --ipc=host --network host \
    --user "$(id -u):$(id -g)" -e HOME=/cache/home "${PASS[@]}" \
    -v "$REPO":/work/repo -v "$CACHE":/cache -w /work/repo \
    "$IMAGE" "$@"
