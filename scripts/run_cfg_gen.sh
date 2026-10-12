#!/usr/bin/env bash
# Build a Linux-native tree-sitter library and run the reentrancy CFG generator.
#
# The .so committed at process_graphs/tree_sitter_codeviews/build/my-languages.so is a
# macOS arm64 Mach-O binary and cannot load on Linux. TREE_SITTER_LIB_DIR redirects the
# loader to a platform-local build directory; custom_parser._initialize_languages() then
# compiles the vendored grammar on first use because no library exists at that path yet.
set -eu

REPO="/home/zhao/SmartContract/ge-sc-llm"
export TREE_SITTER_LIB_DIR="${REPO}/build/linux-x86_64"
mkdir -p "${TREE_SITTER_LIB_DIR}"

source /home/zhao/miniconda3/etc/profile.d/conda.sh
conda activate mando
cd "${REPO}"

echo "=== TREE_SITTER_LIB_DIR=${TREE_SITTER_LIB_DIR} ==="
python -m scripts.gen_reentrancy_cfg \
  --source_dir experiments/ge-sc-data/source_code/reentrancy/source_files \
  --output_dir /tmp/reentrancy_cfg_regen \
  --compare_dir experiments/ge-sc-data/source_code/reentrancy/cfg

echo "=== built library ==="
file "${TREE_SITTER_LIB_DIR}/my-languages.so"
