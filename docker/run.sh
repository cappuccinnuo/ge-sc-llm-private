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
# Reuse the trusted CA bundle from WSL Ubuntu.
HOST_CA=/etc/ssl/certs/ca-certificates.crt

if [ ! -r "$HOST_CA" ]; then
    echo "Missing host CA bundle: $HOST_CA" >&2
    exit 1
fi

PASS+=(
    -v "$HOST_CA:/cache/host-ca-bundle.pem:ro"
    -e REQUESTS_CA_BUNDLE=/cache/host-ca-bundle.pem
    -e CURL_CA_BUNDLE=/cache/host-ca-bundle.pem
    -e SSL_CERT_FILE=/cache/host-ca-bundle.pem
)

for name in http_proxy https_proxy no_proxy all_proxy HTTP_PROXY HTTPS_PROXY NO_PROXY ALL_PROXY HF_ENDPOINT; do
    [ -n "${!name:-}" ] && PASS+=(-e "$name")
done
[ -f "$HOME/.gitconfig" ] && PASS+=(-v "$HOME/.gitconfig:/cache/home/.gitconfig:ro")

# ScholarTools CA certificate
if [ -f "$CACHE/scholar-ca-bundle.pem" ]; then
    PASS+=(
        -e SSL_CERT_FILE=/cache/scholar-ca-bundle.pem
        -e GIT_SSL_CAINFO=/cache/scholar-ca-bundle.pem
        -e REQUESTS_CA_BUNDLE=/cache/scholar-ca-bundle.pem
        -e CURL_CA_BUNDLE=/cache/scholar-ca-bundle.pem
    )
fi
exec docker run --rm "${TTY[@]}" --gpus all --ipc=host --network host \
    --user "$(id -u):$(id -g)" -e HOME=/cache/home "${PASS[@]}" \
    -v "$REPO":/work/repo -v "$CACHE":/cache -w /work/repo \
    "$IMAGE" "$@"
