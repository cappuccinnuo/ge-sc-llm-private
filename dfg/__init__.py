"""DFG augmentation of HCG graphs: analysis, graph layers, models and training.

Layers (each depends only on those above it)::

    dfg.schema     relation vocabulary and profiles
    dfg.analysis   source-level analysis of Solidity files
    dfg.graph      L1-L3 augmentation of an HCG
    dfg.model      HGT models over augmented graphs
    dfg.inputs     HCG datasets -> per-task inputs (sources, version metadata)
    dfg.store      building the augmented graph store
"""
__version__ = "2.0.0"
