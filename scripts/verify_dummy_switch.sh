#!/usr/bin/env bash
# Build the corpus both ways and print the figures that distinguish them, so the
# add_dummy_edges decision rests on evidence rather than on one matching scalar.
set -u
source /home/zhao/miniconda3/etc/profile.d/conda.sh
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm
export TREE_SITTER_LIB_DIR=$PWD/build/linux-x86_64
BASE=experiments/ge-sc-data/source_code/reentrancy

probe () {
  local tag="$1"; local dir="$2"
  echo "=========== ${tag} ==========="
  python -m scripts.gen_reentrancy_cfg --source_dir "${BASE}/source_files" \
    --output_dir "${dir}" 2>&1 | grep -E "^Generated"
  python scripts/inspect_regen.py "${dir}" 2>&1 \
    | grep -E "total nodes|total edges"
  python - "$dir" <<'PY'
import sys, glob, networkx as nx
from collections import Counter
et = Counter()
for p in glob.glob(sys.argv[1] + "/*.gpickle"):
    g = nx.read_gpickle(p)
    for _, _, d in g.edges(data=True):
        et[d.get("edge_type")] += 1
main = {t: n for t, n in et.items() if n > 5}
print(f"  edge types: {len(et)}  (>5 edges: {len(main)})  paper ceiling 5")
for t, n in et.most_common():
    print(f"    {str(t):24s} {n}")
PY
  echo
}

MANDO_DUMMY_EDGES=0 probe "add_dummy_edges OFF (new default, repo original)" /tmp/probe_off
MANDO_DUMMY_EDGES=1 probe "add_dummy_edges ON  (what earlier results used)" /tmp/probe_on

echo "paper appendix C: 18,312 nodes / 19,267 edges / max 5 edge types"
