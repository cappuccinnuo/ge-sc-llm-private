#!/usr/bin/env bash
# Compare the graph-construction files between MANDO (ge-sc) and MANDO-HGT
# (ge-sc-transformer), then show how MANDO-HGT fuses CFG and CG into the
# heterogeneous contract graph.
set -u
cd /tmp/mando-upstream || exit 1

FILES="call_graph_generator.py control_flow_graph_generator.py combination_call_graph_and_control_flow_graph_helper.py"

echo "################ identical or not ################"
for f in $FILES; do
  A="ge-sc-transformer/process_graphs/${f}"
  B="ge-sc/process_graphs/${f}"
  if [ ! -f "$A" ] || [ ! -f "$B" ]; then
    echo "MISSING  ${f}"
    continue
  fi
  n=$(diff "$A" "$B" | grep -cE '^[<>]')
  if [ "$n" -eq 0 ]; then
    echo "SAME  ${f}"
  else
    echo "DIFF  ${f}   (${n} changed lines)"
  fi
done

echo
echo "################ MANDO-HGT: edge/node types in the call graph ################"
grep -n "edge_type=\|node_type = \|node_type=" ge-sc-transformer/process_graphs/call_graph_generator.py | head -25

echo
echo "################ MANDO-HGT: the fusion helper, __main__ ################"
sed -n '/^if __name__/,$p' ge-sc-transformer/process_graphs/combination_call_graph_and_control_flow_graph_helper.py
