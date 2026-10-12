#!/usr/bin/env bash
# Fetch the exact tree-sitter-solidity grammar pinned by the repo's gitlink.
#
# The repo committed vendor/tree-sitter-solidity as a submodule gitlink but never
# committed a .gitmodules file, so `git clone` leaves the directory empty and there
# is no recorded URL. The pinned commit SHA is still recoverable from the tree entry,
# which is what this script resolves against the known upstream candidates.
set -u

SHA="9004b86531cb424bd379424cf7266a4585f2af7d"
VENDOR_DIR="/home/zhao/SmartContract/ge-sc-llm/process_graphs/tree_sitter_codeviews/vendor"
TARGET="${VENDOR_DIR}/tree-sitter-solidity"

CANDIDATES=(
  "https://github.com/JoranHonig/tree-sitter-solidity.git"
  "https://github.com/tree-sitter-grammars/tree-sitter-solidity.git"
)

cd "${VENDOR_DIR}" || exit 1

for URL in "${CANDIDATES[@]}"; do
  echo "=== trying ${URL} ==="
  rm -rf _probe
  mkdir -p _probe
  (
    cd _probe || exit 1
    git init -q .
    git remote add origin "${URL}"
    timeout 180 git fetch -q --depth 1 origin "${SHA}"
  )
  if [ $? -eq 0 ]; then
    echo "FETCH OK from ${URL}"
    (cd _probe && git checkout -q FETCH_HEAD)
    if [ -f "_probe/src/parser.c" ]; then
      echo "parser.c found -> installing into ${TARGET}"
      rm -rf "${TARGET}"
      mv _probe "${TARGET}"
      rm -rf "${TARGET}/.git"
      echo "OK: $(ls "${TARGET}/src" | head -5)"
      exit 0
    else
      echo "WARNING: fetched but no src/parser.c present"
      ls _probe | head
    fi
  else
    echo "fetch failed for ${URL}"
  fi
done

echo "ERROR: could not resolve pinned grammar commit ${SHA}"
exit 1
