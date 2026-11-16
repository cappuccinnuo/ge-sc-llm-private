"""HCG: build MANDO-LLM's heterogeneous contract graphs (CFG + call graph) from source.

Upstream phase of the pipeline. For each vulnerability category of a dataset it turns
raw Solidity files into the HGT inputs the rest of the repository consumes:

    contract_level.gpickle   all contracts, node labels, authors' graph format
    line_level.gpickle       contracts labelled vulnerable only (node-level task)
    graph_labels.json        contract-level targets

The graphs reproduce the format of the MANDO-LLM authors' released graphs exactly
(edge names, DOT-style attribute encoding, line endpoints), so DFG v2, NodeSem and
EdgeSem read them without changes. Node labels follow the public-annotation policy
of Test_code/label_pipeline (2026-10-10).

Layers, top to bottom:

    __main__ / pipeline     CLI and per-category orchestration
    datasets                dataset and category registry (Dataset A: 7 classes)
    sources                 pinned label repositories, annotation loading/projection
    cfg                     tree-sitter CFG + call graph, authors' schema
    labels                  node and contract labels, line-level subset
    features                512-wide tokenizer features
    verify                  comparison against reference graphs
    store                   file I/O and output layout

Run: python -m hcg build --dataset A --categories all
"""

__version__ = "1.0.0"
