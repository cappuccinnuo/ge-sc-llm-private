#!/usr/bin/env bash
# Fetch the vulnerability line annotations the upstream MANDO pipeline consumes.
#
# Upstream merges two sources (ge-sc/process_graphs/control_flow_graph_generator.py):
#   data/smartbug-dataset/vulnerabilities.json          <- SmartBugs curated
#   data/solidifi_buggy_contracts/<bug>/vulnerabilities.json <- SolidiFI injected bugs
# The SmartBugs one ships as JSON already; SolidiFI publishes CSV BugLogs that the
# authors converted to the same JSON shape.
set -u

DEST="/home/zhao/SmartContract/ge-sc-llm/data"
mkdir -p "${DEST}"
cd "${DEST}" || exit 1

echo "=== SmartBugs curated ==="
if [ ! -d smartbug-dataset ]; then
  timeout 300 git clone --depth 1 https://github.com/smartbugs/smartbugs-curated.git smartbug-dataset 2>&1 | tail -2
else
  echo "already present"
fi
ls smartbug-dataset/ 2>/dev/null | head
echo "vulnerabilities.json: $(ls -la smartbug-dataset/vulnerabilities.json 2>/dev/null || echo MISSING)"

echo
echo "=== SolidiFI benchmark ==="
if [ ! -d SolidiFI-benchmark ]; then
  timeout 600 git clone --depth 1 https://github.com/DependableSystemsLab/SolidiFI-benchmark.git SolidiFI-benchmark 2>&1 | tail -2
else
  echo "already present"
fi
echo "--- reentrancy buglog dir ---"
find SolidiFI-benchmark -ipath "*eentran*" -maxdepth 3 -type d 2>/dev/null | head
