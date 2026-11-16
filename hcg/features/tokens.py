"""512-wide tokenizer features: MANDO-LLM's node feature (node['token']).

As recorded in scripts/DFG/dfg_v2/RECON.md for the frozen DFG v2 inputs: the
CodeT5+ 770M tokenizer at a fixed revision, applied to the node's code exactly as
stored (authors' quotes and escapes kept), special tokens added, the first 512 ids
kept and right-padded with the pad id, as float32. Same arithmetic as
scripts/encode_tokenizer_features.encode_ids (scheme 'ids').
"""
import numpy as np

TOKENIZER = "Salesforce/codet5p-770m"
REVISION = "3f7cc6e80aee6612f41253b5ee28f09f86faa35f"
WIDTH = 512


def load_tokenizer(name=TOKENIZER, revision=REVISION):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(name, revision=revision)


def pad_id(tokenizer):
    if tokenizer.pad_token_id is not None:
        return tokenizer.pad_token_id
    return tokenizer.eos_token_id if tokenizer.eos_token_id is not None else 0


def encode_ids(ids, width=WIDTH, pad=0):
    vec = np.full(width, pad, dtype=np.float32)
    ids = list(ids)[:width]
    vec[:len(ids)] = ids
    return vec


def add_tokens(graph, tokenizer, width=WIDTH):
    """Set node['token'] on every node; return (max token length, truncated nodes)."""
    pad, longest, truncated = pad_id(tokenizer), 0, 0
    for _, data in graph.nodes(data=True):
        ids = tokenizer(data.get("code") or "", add_special_tokens=True).input_ids
        longest, truncated = max(longest, len(ids)), truncated + (len(ids) > width)
        data["token"] = encode_ids(ids, width, pad)
    return longest, truncated
