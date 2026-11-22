"""combined: the proposed method, the three enhancements in one model.

    graph   DFG profile G3R (HCG + data-flow layers L1-L3, merged reverse edges)
    edges   EdgeSem G4R-AC: typed directions, the E1 relations (MOD_APPLY, CALL_SITE,
            GUARDS) and the core + context edge attributes in an edge-aware HGT
    nodes   NodeSem S6: CODE + CTX + STATIC + LLM-teacher modalities per node

Layers, top to bottom:

    train   grouped nested CV of the model on one benchmark track (dfg.train engine)
    model   building, initializing and validating the model from the three stages' inputs

The benchmark trains it as profile FULL next to the MANDO-LLM baseline G0
(``python -m benchmark run --profiles G0 FULL``); see ``combined/README.md``.
"""

__version__ = "1.0.0"
PROFILE = "FULL"
GRAPH_PROFILE = "G3R"
EDGE_PROFILE = "G4R-AC"
NODE_CONFIG = "S6"
