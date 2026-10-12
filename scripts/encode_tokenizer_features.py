"""Build node features from an LLM *tokenizer* only - the MANDO-LLM node feature extractor.

This is deliberately NOT scripts/encode_llm_tokens.py. That one runs a full
T5EncoderModel forward pass and mean-pools the hidden states, which the paper lists
as the "LLM Encoder-only" *baseline* (mando-llm.md section 18). The method itself
states the opposite (section 6.2, appendix A):

    "论文没有把节点代码送入完整 LLM Encoder, 而是只使用 LLM Tokenizer"
    Feature extractor | LLM Tokenizer | 不使用完整 LLM Encoder

so node features here come from tokenization alone: no model weights, no forward
pass, no GPU.

FEATURE SIZE. Appendix A pins the node feature size at 512 for both the
contract-level and line-level tasks, which is also the value hard-coded as
`embedding_dim = 512` in sco_models/model_hgt.py for the 'token' and 'inside_token'
branches, and is the same order as MAX_INPUT_LENGTH = 516 in
experiments/token_baselines.py.

INFERRED DETAIL - READ BEFORE QUOTING ANY NUMBER FROM THIS. The paper does not say
how a token id sequence becomes a 512-wide vector, so --scheme exposes the plausible
readings instead of hiding a guess behind a single implementation:

  ids         (default) the token id sequence itself, truncated or right-padded to
              512. Chosen as the default because 512 then reads as a sequence budget,
              which lines up with MAX_INPUT_LENGTH = 516 in token_baselines.py and
              with embedding_dim = 512 in model_hgt.py. It is a reconstruction, not
              something the paper states.
  hashed_bow  ids hashed into 512 buckets, counted, so the feature is order-free and
              bounded regardless of snippet length. Lossy: on the reentrancy corpus
              25 distinct snippets collide onto shared vectors.
  ids_norm    like 'ids' but divided by vocab_size, keeping every entry in [0, 1].
              Information-identical to 'ids'; only the scale differs.

Measured on the line-level task (10-fold, buggy contracts only): ids 99.00 Buggy-F1,
hashed_bow 99.32, ids_norm 97.19. The three are within about two points of each
other on a single seed, so the scheme was NOT picked by score - doing that would be
fitting the choice to the metric. Treat this step as a reproduction uncertainty.
"""
import argparse
import sys
from pathlib import Path

import networkx as nx
import numpy as np
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH = REPO / "experiments/ge-sc-data/source_code/reentrancy/hcg_compressed_graphs.gpickle"


def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--graph", default=str(DEFAULT_GRAPH),
                   help="Labelled HCG to read node['code'] from")
    p.add_argument("--output", default=None)
    p.add_argument("--tokenizer", default="Salesforce/codet5p-770m",
                   help="HuggingFace tokenizer id. The paper uses Solidity-T5, "
                        "StarCoder and CodeT5p-770m")
    p.add_argument("--graph_type", default="hcg")
    p.add_argument("--feature_size", type=int, default=512,
                   help="Node feature width, 512 per appendix A")
    p.add_argument("--scheme", choices=("ids", "hashed_bow", "ids_norm"), default="ids")
    p.add_argument("--coarse_output", default=None,
                   help="Also write contract-level features in the shipped .pt layout")
    p.add_argument("--limit", type=int, default=None)
    return p


def encode_ids(ids, size, pad_id):
    out = np.full(size, pad_id, dtype=np.float32)
    n = min(len(ids), size)
    if n:
        out[:n] = np.asarray(ids[:n], dtype=np.float32)
    return out


def encode_hashed_bow(ids, size):
    out = np.zeros(size, dtype=np.float32)
    for tid in ids:
        out[tid % size] += 1.0
    return out


def main():
    args = build_parser().parse_args()
    graph_path = Path(args.graph)

    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True)
    vocab_size = getattr(tokenizer, "vocab_size", None) or len(tokenizer)
    pad_id = tokenizer.pad_token_id
    if pad_id is None:
        pad_id = tokenizer.eos_token_id if tokenizer.eos_token_id is not None else 0

    print(f"graph      : {graph_path}")
    g = nx.read_gpickle(str(graph_path))
    print(f"nodes      : {g.number_of_nodes()}  edges: {g.number_of_edges()}")
    print(f"tokenizer  : {args.tokenizer}  vocab_size={vocab_size}  pad_id={pad_id}")
    print(f"scheme     : {args.scheme}   feature_size: {args.feature_size}")

    node_ids = list(g.nodes())
    if args.limit:
        node_ids = node_ids[: args.limit]

    lengths = []
    truncated = 0
    for node_id in tqdm(node_ids, unit="node", desc="tokenizing"):
        code = g.nodes[node_id].get("code") or ""
        ids = tokenizer(code, add_special_tokens=True).input_ids
        lengths.append(len(ids))
        if len(ids) > args.feature_size:
            truncated += 1

        if args.scheme == "hashed_bow":
            vec = encode_hashed_bow(ids, args.feature_size)
        elif args.scheme == "ids_norm":
            vec = encode_ids(ids, args.feature_size, pad_id) / float(vocab_size)
        else:
            vec = encode_ids(ids, args.feature_size, pad_id)
        g.nodes[node_id]["token"] = vec

    lengths = np.asarray(lengths)
    print(f"\ntoken lengths: mean {lengths.mean():.1f}  median {int(np.median(lengths))}  "
          f"p95 {int(np.percentile(lengths, 95))}  max {int(lengths.max())}")
    print(f"nodes truncated at {args.feature_size}: {truncated} "
          f"({100.0 * truncated / len(node_ids):.2f}%)")

    tag = args.tokenizer.split("/")[-1]
    out_path = Path(args.output) if args.output else graph_path.parent / (
        f"tokenizer_{args.scheme}_{tag}_{args.graph_type}_compressed_graphs.gpickle"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    nx.write_gpickle(g, str(out_path))
    print(f"wrote node-level graph -> {out_path}")

    if args.coarse_output:
        import torch
        per_file = {}
        buggy = {}
        for node_id in node_ids:
            d = g.nodes[node_id]
            per_file.setdefault(d["source_file"], []).append(d["token"])
            buggy[d["source_file"]] = buggy.get(d["source_file"], False) or bool(
                d.get("node_info_vulnerabilities"))
        names = sorted(per_file)
        source_embedding = torch.tensor(
            np.stack([np.mean(np.stack(per_file[n]), axis=0) for n in names]))
        label = torch.tensor([1 if buggy[n] else 0 for n in names], dtype=torch.int64)
        coarse = Path(args.coarse_output)
        coarse.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"source_embedding": source_embedding, "label": label,
                    "contract_name": names}, str(coarse))
        print(f"wrote contract-level features -> {coarse} "
              f"({tuple(source_embedding.shape)}, {int(label.sum())} buggy)")


if __name__ == "__main__":
    main()
