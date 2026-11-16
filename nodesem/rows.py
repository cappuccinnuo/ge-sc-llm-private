"""TODO docstring."""
import hashlib

import numpy as np

from dfg.graph.env import ENV_KEYS
from dfg.schema import AUX_NODE_TYPES


# ----------------------------------------------------------------------
# node_sem/carrier (picked: vector_sha, row_key)
def vector_sha(value):
    value = np.asarray(value)
    if value.dtype != np.float32 or value.ndim != 1 or not np.isfinite(value).all():
        raise ValueError("Expected finite one-dimensional float32 carrier")
    return hashlib.sha256(value.tobytes(order="C")).hexdigest()

def row_key(node_id, attrs):
    if attrs["node_type"] in AUX_NODE_TYPES:
        key = attrs["code"]
        if attrs["node_type"] != "env_source" or key not in ENV_KEYS:
            raise ValueError("Unknown auxiliary node feature identity")
        return "env:{}:{}".format(attrs["source_file"], key)
    if isinstance(node_id, bool) or not isinstance(node_id, (int, str)):
        raise ValueError("Only integer/string original graph IDs are supported")
    return node_id
