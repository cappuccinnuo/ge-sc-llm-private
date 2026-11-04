"""Fixed-graph attention readout controlled experiment; no new DDG semantics."""
VERSION="author-hcg-attention-readout-paper-v1"
PAIR_VERSION="saved-mean-zero-readout-v1"
VARIANTS=("HCG","HCG_DDG_GUARD")
READOUT=dict(version="file-softmax-linear-zero-v1",algorithm="per_file_softmax_linear",
             parameter="readout_vector",initialization="all_zero_no_rng_draw",score_bias=False,
             normalization="all_original_nodes_of_one_source_file",additional_parameters=128)
