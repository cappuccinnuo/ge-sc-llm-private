#!/usr/bin/env bash
# Fetch the vulnerability line annotations the graph build consumes, pinned to the
# exact commits the seven-category baseline was built from. Idempotent.
#
#   smartbug-dataset/vulnerabilities.json                  SmartBugs curated
#   SolidiFI-benchmark/buggy_contracts/<bug>/BugLog_N.csv   SolidiFI injected bugs
#
# Destination: $MANDO_DATA_DIR if set, else <repo>/data (git-ignored). This replaces
# scripts/fetch_vuln_labels.sh for new builds; that one is left unchanged because
# sealed manifests pin its hash, and it clones into a hard-coded path, unpinned.
set -eu

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST="${MANDO_DATA_DIR:-${REPO}/data}"
SMARTBUGS_COMMIT=230e649123477eff332742a59a1c7cc6dc286cab   # 2024-06-16
SOLIDIFI_COMMIT=4b0573e1b3f7031396de6f48f7f3e7380222ad3a    # 2020-06-23

fetch () {
  local url="$1" dir="$2" commit="$3"
  if [ ! -d "${DEST}/${dir}/.git" ]; then
    git init -q "${DEST}/${dir}"
    git -C "${DEST}/${dir}" remote add origin "${url}"
  fi
  if [ "$(git -C "${DEST}/${dir}" rev-parse -q --verify HEAD 2>/dev/null)" != "${commit}" ]; then
    git -C "${DEST}/${dir}" fetch -q --depth 1 origin "${commit}"
    git -C "${DEST}/${dir}" checkout -q --detach FETCH_HEAD
  fi
  echo "${dir}: $(git -C "${DEST}/${dir}" rev-parse HEAD)"
}

mkdir -p "${DEST}"
fetch https://github.com/smartbugs/smartbugs-curated.git smartbug-dataset "${SMARTBUGS_COMMIT}"
fetch https://github.com/DependableSystemsLab/SolidiFI-benchmark.git SolidiFI-benchmark "${SOLIDIFI_COMMIT}"
test -f "${DEST}/smartbug-dataset/vulnerabilities.json"
test -d "${DEST}/SolidiFI-benchmark/buggy_contracts/Re-entrancy"
echo "label sources ready under ${DEST}"
