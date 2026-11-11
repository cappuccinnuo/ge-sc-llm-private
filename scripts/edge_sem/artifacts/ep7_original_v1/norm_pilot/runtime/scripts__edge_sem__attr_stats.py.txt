"""Descriptive-only reporting. This is the sole EP4 label-reading function.

Neither the reported labels nor these statistics may select attributes,
core indices, samples, thresholds or training configurations.
"""
from collections import defaultdict
import numpy as np
from .attrs import EDGE_FEATURE_NAMES, GROUPS


def descriptive_statistics(rows, attrs, graph):
    groups=defaultdict(list)
    for row in rows:groups[row["relation"]].append(row)
    output={}
    totals=dict(edges=len(rows),all_zero_edges=sum(not attrs[r["key"]].any() for r in rows))
    totals["all_zero_fraction"]=totals["all_zero_edges"]/len(rows) if rows else None
    for rel,rs in sorted(groups.items()):
        matrix=np.stack([attrs[r["key"]] for r in rs])
        classes=defaultdict(list)
        for r in rs:
            node=graph.nodes[r["dst"]]
            # Exact frozen author rule from sco_models.graph_utils.get_node_labels:
            # original node label is 0 iff node_info_vulnerabilities is None.
            # Auxiliary environment nodes are never assigned supervision here.
            if node["node_type"]=="env_source" or "node_info_vulnerabilities" not in node:
                label="unlabelled"
            else:label="positive" if node["node_info_vulnerabilities"] is not None else "negative"
            classes[label].append(attrs[r["key"]])
        item=dict(edges=len(rs),all_zero_edges=int((matrix.sum(axis=1)==0).sum()),
                  all_zero_fraction=float((matrix.sum(axis=1)==0).mean()),
                  bits={name:dict(ones=int(matrix[:,i].sum()),fraction=float(matrix[:,i].mean()))
                        for i,name in enumerate(EDGE_FEATURE_NAMES)},
                  groups={name:dict(nonzero_edges=int(matrix[:,indices].any(axis=1).sum()),
                                    fraction=float(matrix[:,indices].any(axis=1).mean()))
                          for name,indices in GROUPS.items()},
                  by_original_target_label={})
        for label,values in classes.items():
            m=np.stack(values)
            item["by_original_target_label"][label]=dict(edges=len(values),
                bit_fractions={name:float(m[:,i].mean()) for i,name in enumerate(EDGE_FEATURE_NAMES)})
        output[rel]=item
    return dict(totals=totals,by_relation=output,label_use="descriptive_only_after_core_selection",
                target_label_policy="author original: None=0, non-None=1; env excluded; not L-audit")


