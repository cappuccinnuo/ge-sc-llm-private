#!/usr/bin/env bash
# CP6.0: reproduce the recorded absolute layout inside Claude's cloud container only.
# The user's machine already has this layout; do not run this script there.
# Every binary and input is still SHA256-checked by the module itself.
set -euo pipefail
REPO=${1:?repo checkout}; SOLC_DIR=${2:?dir with solc-<version> files}; SBC=${3:?smartbugs-curated clone}; VENV=${4:?production venv}
mkdir -p /home/zhao/SmartContract/ge-sc-llm/data /home/zhao/.solc-select/artifacts /home/claude/env
ln -sfn "$REPO" /home/zhao/SmartContract/ge-sc-llm-compile
ln -sfn "$SBC" /home/zhao/SmartContract/ge-sc-llm/data/smartbug-dataset
for f in "$SOLC_DIR"/solc-*; do v=${f##*/solc-}; mkdir -p /home/zhao/.solc-select/artifacts/solc-$v; ln -sfn "$f" /home/zhao/.solc-select/artifacts/solc-$v/solc-$v; done
# Tests recognise the production environment by its directory name.
ln -sfn "$VENV" /home/claude/env/compile-repair-production
echo "Run tests with: HOME=/home/zhao TREE_SITTER_LIB_DIR=<dir with my-languages.so> /home/claude/env/compile-repair-production/bin/python -B -m pytest compile_repair/tests"
