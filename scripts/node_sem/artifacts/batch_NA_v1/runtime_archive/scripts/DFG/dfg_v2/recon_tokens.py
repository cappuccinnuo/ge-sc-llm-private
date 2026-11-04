"""Prompt 0 read-only token provenance/sample audit; no feature assignment."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import random
import time

import numpy as np

from scripts.DFG.integration.rebuild import DEFAULT_MANIFEST
from scripts.DFG.integration.io import checked, read_json, sha256
from scripts.DFG.experiments.prepare import TOKENIZER, REVISION, cached_tokenizer, tokenizer_assets
from scripts.encode_tokenizer_features import encode_ids
from scripts.labeling_v2.safe_graph import read_graph


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def array_digest(value):
    value = np.asarray(value)
    return hashlib.sha256(str(value.dtype).encode() + str(value.shape).encode() + value.tobytes()).hexdigest()


def run(reference, output, sample_size=200, seed=0):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Refusing existing audit output: " + str(output))
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    reference = Path(reference).resolve()
    reference_sha = read_json(reference.with_name("manifest.seal.json"))["sha256"]
    checked(reference, reference_sha)
    manifest = read_json(reference)
    inputs = {str(reference): reference_sha}
    tasks = []
    for rec in manifest["tasks"]:
        task_path = checked(rec["source_task_manifest"], rec["source_task_sha256"])
        task = read_json(task_path)
        graph_rec = task["graphs"]["HCG"]
        graph_path = checked(graph_rec["path"], graph_rec["sha256"])
        source_path = checked(rec["source_metadata_manifest"], rec["source_metadata_sha256"])
        source_records = read_json(source_path)["sources"]
        inputs[str(task_path)] = rec["source_task_sha256"]
        inputs[str(graph_path)] = graph_rec["sha256"]
        inputs[str(source_path)] = rec["source_metadata_sha256"]
        for asset, digest in task["feature"]["asset_hashes"].items():
            checked(asset, digest)
            inputs[asset] = digest
        if task["feature"]["model"] != TOKENIZER or task["feature"]["revision"] != REVISION:
            raise ValueError("Frozen tokenizer identity mismatch")
        graph = read_graph(graph_path)
        candidates = list(graph.nodes())
        sample = random.Random(seed).sample(candidates, min(sample_size, len(candidates)))
        selected = []
        for node in sample:
            data = graph.nodes[node]
            source = source_records[data["source_file"]]
            checked(source["path"], source["sha256"])
            inputs[source["path"]] = source["sha256"]
            selected.append({"node_id": node, "node_id_type": type(node).__name__,
                "source_file": data["source_file"], "source_path": source["path"],
                "source_sha256": source["sha256"], "node_type": data["node_type"],
                "code": data.get("code") or "", "code_sha256": hashlib.sha256(
                    (data.get("code") or "").encode("utf8")).hexdigest(),
                "frozen_token_sha256": array_digest(data.get("token"))})
        tasks.append((rec["task_id"], task, graph_path, graph, selected))
    output.mkdir(parents=True)
    selection = {"reference": str(reference), "reference_sha256": reference_sha,
        "seed": seed, "requested_per_task": sample_size,
        "sampling": "random.Random(seed).sample(list(graph.nodes()), min(count, len(graph))); reset per task",
        "tasks": [{"task_id": tid, "graph_path": str(gp), "selected": selected}
                  for tid, task, gp, graph, selected in tasks]}
    dump(output / "selection.json", selection)
    dump(output / "selection.seal.json", {"sha256": sha256(output / "selection.json")})
    started = time.monotonic()
    tok = cached_tokenizer()
    pad = tok.pad_token_id
    if pad is None:
        pad = tok.eos_token_id if tok.eos_token_id is not None else 0
    if pad != 0:
        raise ValueError("Frozen pad token mismatch")
    summaries = []
    for tid, task, graph_path, graph, selected in tasks:
        pairs, mismatches, stored_vectors, new_vectors = [], [], [], []
        for row in selected:
            vector = np.asarray(graph.nodes[row["node_id"]].get("token"))
            ids = tok(row["code"], add_special_tokens=True).input_ids
            encoded = encode_ids(ids, 512, pad)
            exact = (vector.dtype == np.float32 and vector.shape == (512,)
                     and bool(np.array_equal(vector, encoded)))
            indices = np.flatnonzero(vector != encoded).tolist() if vector.shape == encoded.shape else None
            item = dict(row, exact_match=exact, stored_dtype=str(vector.dtype),
                        stored_shape=list(vector.shape), tokenized_length=len(ids),
                        reencoded_token_sha256=array_digest(encoded), differing_positions=indices)
            pairs.append(item)
            if not exact:
                mismatches.append(item)
            stored_vectors.append(vector)
            new_vectors.append(encoded)
        all_meta = Counter((str(np.asarray(d.get("token")).dtype),
                            str(tuple(np.asarray(d.get("token")).shape)))
                           for _,d in graph.nodes(data=True))
        dest = output / tid
        dest.mkdir()
        dump(dest / "nodes.json", pairs)
        dump(dest / "mismatches.json", mismatches)
        np.savez_compressed(str(dest / "vectors.npz"),
                           stored=np.stack(stored_vectors), reencoded=np.stack(new_vectors))
        summary = {"task_id": tid, "graph_path": str(graph_path), "graph_sha256": sha256(graph_path),
            "population_nodes": len(graph), "sampled_nodes": len(selected),
            "exact_matches": len(selected)-len(mismatches), "mismatches": len(mismatches),
            "match_fraction": float(len(selected)-len(mismatches))/len(selected),
            "sample_truncated_nodes": sum(x["tokenized_length"] > 512 for x in pairs),
            "all_node_feature_metadata": [{"dtype": k[0], "shape": k[1], "count": v}
                                           for k,v in sorted(all_meta.items())],
            "sample_file_count": len({x["source_file"] for x in selected}),
            "node_evidence": str(dest / "nodes.json"), "vectors": str(dest / "vectors.npz"),
            "frozen_feature_provenance": task["feature"]}
        dump(dest / "summary.json", summary)
        summaries.append(summary)
        print(tid + ": " + str(summary["exact_matches"]) + "/" + str(len(selected)), flush=True)
    for path, digest in inputs.items():
        checked(path, digest)
    result = {"version": "dfg-v2-p0-token-audit-v1", "tasks": summaries,
        "all_samples_exact": all(x["mismatches"] == 0 for x in summaries),
        "total_sampled_nodes": sum(x["sampled_nodes"] for x in summaries),
        "tokenizer": {"model": TOKENIZER, "revision": REVISION, "class": type(tok).__name__,
            "local_snapshot": str(Path.home()/".cache/huggingface/hub/models--Salesforce--codet5p-770m/snapshots"/REVISION),
            "assets": tokenizer_assets(), "special_tokens": tok.special_tokens_map,
            "special_ids": {"pad": tok.pad_token_id, "bos": tok.bos_token_id, "eos": tok.eos_token_id,
                            "unk": tok.unk_token_id}, "vocab_size": tok.vocab_size},
        "recipe": {"source": "node.code exactly as serialized; no unquoting", "add_special_tokens": True,
            "tokenization_truncation": False, "vector": "encode_ids(ids, 512, pad_id)",
            "truncation": "slice first 512 ids AFTER special tokens; truncated EOS need not be retained",
            "padding": "right pad with pad_token_id", "dtype": "float32", "width": 512,
            "normalization": False, "weights_loaded": False},
        "feature_provenance": "locally reconstructed token IDs on released author graph, not author-supplied embeddings",
        "inputs": inputs, "inputs_unchanged": True, "network_used": False,
        "model_weights_loaded": False, "training_executed": False,
        "elapsed_seconds": time.monotonic()-started,
        "script_sha256": sha256(Path(__file__).resolve())}
    dump(output / "summary.json", result)
    dump(output / "summary.seal.json", {"sha256": sha256(output / "summary.json")})
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference-manifest", default=str(DEFAULT_MANIFEST))
    p.add_argument("--output", required=True)
    p.add_argument("--sample-size", type=int, default=200)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()
    result = run(args.reference_manifest, args.output, args.sample_size, args.seed)
    if not result["all_samples_exact"]:
        raise SystemExit("Token mismatch: stop before later prompts")


if __name__ == "__main__":
    main()
