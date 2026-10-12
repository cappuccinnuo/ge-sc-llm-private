"""Encode each CFG node's source snippet with an LLM and store it as node['token'].

This is the producer side of MANDO-LLM's semantic enhancement. The repository ships
the consumer side only:

  sco_models/model_hgt.py   node_feature='inside_token' -> get_node_token(nx_graph)
                            reads node['token'] and infers in_size from its width
  sco_models/graph_utils.py get_node_token / map_node_token

but nothing anywhere writes node['token'], and no script produces the encode_*.pt
files referenced (commented out) in experiments/token_baselines.py. This script fills
that gap.

The recipe follows the authors' own commented code in token_baselines.py:

    input_ids = tokenizer(node['code'], max_length=516,
                          padding="max_length", truncation=True).input_ids
    last_hidden_states = model(input_ids=input_ids).last_hidden_state   # [B, L, H]
    emb = torch.mean(last_hidden_states, dim=1)                        # pool

POOLING: the default 'mean' reproduces that line literally - pad to max_length, call
the encoder with input_ids only (no attention mask, as the authors do), and average
every position including padding. That looked suspect at first, since the median node
is 48 characters (~15 tokens) against max_length=516, so ~97% of the averaged
positions are padding. Measured on a 64-node sample it is not degenerate: T5's encoder
is bidirectional, padding positions still attend to the real tokens, and the resulting
vectors stay well separated (56/64 distinct, per-dim std 0.183 versus 57/64 and 0.122
for masked_mean). 'masked_mean' is the more principled variant, averaging real tokens
only and passing an attention mask; it is kept as an option for ablation. Under
masked_mean the padding strategy cannot change the result, so batches are padded
dynamically instead of always to max_length.

Output is a new graph named like the authors' convention,
  encode_token_<model>_<graph_type>_compressed_graphs.gpickle
leaving the input graph untouched. --coarse_output additionally writes the
contract-level file in the shipped .pt layout, {'source_embedding': [N, H],
'label': [N]}, produced the same way generate_coarse_grained_data() does it:
mean of a contract's node embeddings.
"""
import argparse
import time
from pathlib import Path

import networkx as nx
import numpy as np
import torch
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH = REPO / "experiments/ge-sc-data/source_code/reentrancy/cfg_compressed_graphs.gpickle"


def build_parser():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--graph", default=str(DEFAULT_GRAPH),
                   help="Labelled compressed graph to read node['code'] from")
    p.add_argument("--output", default=None,
                   help="Output graph path (default: alongside the input, authors' naming)")
    p.add_argument("--model", default="Salesforce/codet5p-770m",
                   help="HuggingFace encoder id. The authors report codet5p-770m, "
                        "solidity-t5, starcoder and starcoderbase-1b")
    p.add_argument("--graph_type", default="cfg",
                   help="Tag used when composing the default output name")
    p.add_argument("--pooling", choices=("mean", "masked_mean", "cls"), default="mean",
                   help="mean reproduces the authors' line literally, padding included "
                        "and no attention mask (default); masked_mean averages real "
                        "tokens only; cls takes the first position")
    p.add_argument("--max_length", type=int, default=516,
                   help="Token budget per node, 516 in the authors' code")
    p.add_argument("--batch_size", type=int, default=8)
    p.add_argument("--device", default=None)
    p.add_argument("--fp16", action="store_true", default=None,
                   help="Half precision (default: on for CUDA, off for CPU)")
    p.add_argument("--no_fp16", dest="fp16", action="store_false")
    p.add_argument("--coarse_output", default=None,
                   help="Also write contract-level embeddings in the shipped .pt layout")
    p.add_argument("--limit", type=int, default=None,
                   help="Encode only the first N nodes; for smoke tests")
    return p


def load_encoder(model_id, device, fp16):
    from transformers import AutoTokenizer, AutoConfig

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    config = AutoConfig.from_pretrained(model_id, trust_remote_code=True)
    is_t5 = getattr(config, "model_type", "") in ("t5", "codet5p", "mt5")

    if is_t5:
        from transformers import T5EncoderModel
        model = T5EncoderModel.from_pretrained(model_id, trust_remote_code=True)
    else:
        # StarCoder and friends are decoder-only; AutoModel still exposes
        # last_hidden_state, which is what the pooling below needs.
        from transformers import AutoModel
        model = AutoModel.from_pretrained(model_id, trust_remote_code=True)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = model.half() if fp16 else model.float()
    return tokenizer, model.to(device).eval()


def pool(last_hidden_state, attention_mask, mode):
    if mode == "cls":
        return last_hidden_state[:, 0, :]
    if mode == "mean":
        # Literal reproduction of the authors' line: every position counts,
        # padding included.
        return last_hidden_state.mean(dim=1)
    mask = attention_mask.unsqueeze(-1).to(last_hidden_state.dtype)
    summed = (last_hidden_state * mask).sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1e-6)
    return summed / counts


def main():
    args = build_parser().parse_args()
    device = args.device or ("cuda:0" if torch.cuda.is_available() else "cpu")
    fp16 = args.fp16 if args.fp16 is not None else device.startswith("cuda")

    graph_path = Path(args.graph)
    print(f"graph  : {graph_path}")
    g = nx.read_gpickle(str(graph_path))
    print(f"nodes  : {g.number_of_nodes()}  edges: {g.number_of_edges()}")

    node_ids = list(g.nodes())
    if args.limit:
        node_ids = node_ids[: args.limit]
    missing = [n for n in node_ids if not g.nodes[n].get("code")]
    if missing:
        print(f"WARNING: {len(missing)} nodes have no 'code' and will get a zero vector")

    print(f"model  : {args.model}   device: {device}   fp16: {fp16}")
    print(f"pooling: {args.pooling}   max_length: {args.max_length}   batch: {args.batch_size}")
    tokenizer, model = load_encoder(args.model, device, fp16)

    # Group similar lengths together so dynamic padding wastes as little as possible.
    order = sorted(node_ids, key=lambda n: len(g.nodes[n].get("code") or ""))
    padding = "max_length" if args.pooling == "mean" else True

    started = time.time()
    hidden = None
    with torch.no_grad():
        for i in tqdm(range(0, len(order), args.batch_size), unit="batch", desc="encoding"):
            batch_ids = order[i: i + args.batch_size]
            texts = [g.nodes[n].get("code") or "" for n in batch_ids]
            enc = tokenizer(texts, return_tensors="pt", max_length=args.max_length,
                            padding=padding, truncation=True)
            input_ids = enc["input_ids"].to(device)
            attention_mask = enc["attention_mask"].to(device)
            if args.pooling == "mean":
                # Match the authors' call exactly: model(input_ids=input_ids), with no
                # attention mask, so padding positions participate in attention too.
                out = model(input_ids=input_ids)
            else:
                out = model(input_ids=input_ids, attention_mask=attention_mask)
            emb = pool(out.last_hidden_state, attention_mask, args.pooling)
            emb = emb.float().cpu().numpy().astype(np.float32)
            hidden = emb.shape[-1]
            for node_id, vec in zip(batch_ids, emb):
                g.nodes[node_id]["token"] = vec

    elapsed = time.time() - started
    print(f"\nencoded {len(order)} nodes in {elapsed:.1f}s  ({len(order)/max(elapsed,1e-9):.1f} nodes/s)")
    print(f"embedding dim: {hidden}")

    model_tag = args.model.split("/")[-1]
    if args.output:
        out_path = Path(args.output)
    else:
        out_path = graph_path.parent / (
            f"encode_token_{model_tag}_{args.graph_type}_compressed_graphs.gpickle"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    nx.write_gpickle(g, str(out_path))
    print(f"wrote node-level graph -> {out_path}")

    if args.coarse_output:
        # Contract embedding = mean of its node embeddings, matching
        # token_baselines.generate_coarse_grained_data.
        per_file = {}
        for node_id in order:
            data = g.nodes[node_id]
            per_file.setdefault(data["source_file"], []).append(data["token"])
        names = sorted(per_file)
        source_embedding = torch.tensor(
            np.stack([np.mean(np.stack(per_file[n]), axis=0) for n in names])
        )
        label = torch.tensor([
            1 if any(
                g.nodes[n].get("node_info_vulnerabilities")
                for n in order if g.nodes[n]["source_file"] == name
            ) else 0
            for name in names
        ], dtype=torch.int64)
        coarse_path = Path(args.coarse_output)
        coarse_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"source_embedding": source_embedding, "label": label,
                    "contract_name": names}, str(coarse_path))
        print(f"wrote contract-level embeddings -> {coarse_path} "
              f"({tuple(source_embedding.shape)}, {int(label.sum())} buggy)")


if __name__ == "__main__":
    main()
