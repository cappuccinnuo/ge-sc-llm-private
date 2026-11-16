"""EdgeSem: edge semantic enhancement of the DFG heterogeneous graph.

Layers (each depends only on the ones above it, on ``dfg`` and on ``nodesem.facts``):

    schema.py             relations, families, profiles, frozen attribute columns, P2
    graph/                F4 = F3 + MOD_APPLY / CALL_SITE / GUARDS edges
        calls.py              call-site resolution
        guards.py             guard evidence and the guard correspondence audit
        f4.py                 per-file F4 records; add_edges
    attributes/           uint8[74] edge attributes
        layout.py             bit layout, validity rules, edge row keys
        sources.py            CFG dominance/reachability and declaration sources
        compute.py            attribute vectors of every F3/F4 edge
    pipeline.py, store.py build a task's F4 edges and attributes into data/edgesem
    model/                edge-aware HGT
        relations.py          per-profile relation materialization
        init.py               typed parameter copy from the G3R anchor
        layers.py             EdgeAwareHGTLayer, edge encoder, classifiers
        placebo.py            relation rewiring and attribute permutation placebos
        build.py              make_edge_model, validate_registration
    train.py              P2 grouped nested CV on the dfg.train folds, labels and tokens
"""
