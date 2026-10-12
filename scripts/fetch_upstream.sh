#!/usr/bin/env bash
# Clone the predecessor MANDO repos for reference only (read-only comparison).
set -eu
DEST="/tmp/mando-upstream"
mkdir -p "${DEST}"
cd "${DEST}"

for REPO in ge-sc ge-sc-transformer; do
  if [ ! -d "${REPO}" ]; then
    echo "=== cloning ${REPO} ==="
    timeout 300 git clone --depth 1 "https://github.com/MANDO-Project/${REPO}.git" "${REPO}"
  else
    echo "=== ${REPO} already present ==="
  fi
done

echo "=== ge-sc/process_graphs ==="
ls -la "${DEST}/ge-sc/process_graphs" 2>/dev/null || echo "missing"
echo "=== ge-sc-transformer/process_graphs ==="
ls -la "${DEST}/ge-sc-transformer/process_graphs" 2>/dev/null || echo "missing"
