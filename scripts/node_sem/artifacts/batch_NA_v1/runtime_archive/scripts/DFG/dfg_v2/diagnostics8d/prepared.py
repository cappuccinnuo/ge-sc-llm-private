"""Materialize audited same-position token views once, without model forwards."""
import argparse
import hashlib
from pathlib import Path
import numpy as np
from scripts.DFG.dfg_v2.diagnostics8c.common import read, write_new, checked_plan
from scripts.DFG.dfg_v2.tasks import checked_ref
from scripts.DFG.integration.io import sha256
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.dfg_v2.tokens import TokenEncoder
from .renaming import rewrite_node

MODES = ("B_full", "B_matched", "C_matched")


def ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha256(path))


def vector_sha256(value):
    value = np.asarray(value)
    if value.dtype != np.float32 or value.shape != (512,) or not np.isfinite(value).all():
        raise ValueError("Frozen token row must be finite float32[512]")
    return hashlib.sha256(value.tobytes(order="C")).hexdigest()


def load_view(prepared_path, task_id, mode, source_plan_path):
    prepared_path = Path(prepared_path).resolve()
    manifest = read(prepared_path)
    if sha256(prepared_path) != read(prepared_path.with_name("manifest.seal.json"))["sha256"]:
        raise ValueError("Prepared token view seal mismatch")
    if mode not in MODES or manifest["source_plan"] != ref(source_plan_path):
        raise ValueError("Prepared intervention source plan/mode differs")
    entry = manifest["tasks"][task_id]["views"][mode]
    view = read(checked_ref(entry["manifest"]))
    if view["task_id"] != task_id or view["mode"] != mode:
        raise ValueError("Prepared token view task/mode mismatch")
    plan = checked_plan(source_plan_path)
    task = plan["tasks"][task_id]
    info = read(checked_ref(task["prepared"]["0/1"]))
    if view["source_refs"] != task["record"]["sources"] or view["frozen_graph"] != info["profiles"]["G0"]["graph"]:
        raise ValueError("Prepared view graph/source binding differs")
    from scripts.DFG.dfg_v2.diagnostics8c.inference_summary import TOKEN_KEYS
    for key in TOKEN_KEYS:
        if key in task["record"]["feature"] and view["tokenizer"].get(key) != task["record"]["feature"][key]:
            raise ValueError("Prepared tokenizer recipe differs: " + key)
    if (view["tokenizer"].get("network_used") is not False
            or view["tokenizer"].get("model_weights_loaded") is not False
            or set(view["mappings"]) != set(task["record"]["sources"])
            or entry["changed_nodes"] != len(view["rows"])):
        raise ValueError("Prepared tokenizer/scope/count differs")
    vectors = np.load(str(checked_ref(entry["data"])), allow_pickle=False)["vectors"]
    if vectors.dtype != np.float32 or vectors.shape != (len(view["rows"]), 512):
        raise ValueError("Prepared vector shape/dtype differs")
    if not np.isfinite(vectors).all():
        raise ValueError("Nonfinite prepared token values")
    keys = [(row["file"], row["original_graph_node_id"]) for row in view["rows"]]
    if len(keys) != len(set(keys)) or [r["vector_row"] for r in view["rows"]] != list(range(len(keys))):
        raise ValueError("Prepared node identity/row alignment differs")
    for row, vector in zip(view["rows"], vectors):
        if vector_sha256(vector) != row["renamed_vector_sha256"]:
            raise ValueError("Prepared vector digest differs")
        if row["before_token_length"] != row["after_token_length"]:
            raise ValueError("Prepared full token lengths differ")
        proof = row["position_proof"]
        if (proof.get("unedited_token_ids_equal") is not True
                or proof.get("occurrence_token_positions_equal") is not True
                or proof.get("full_token_count") != row["before_token_length"]):
            raise ValueError("Prepared token position proof failed")
    return view, vectors, dict(manifest=ref(prepared_path), view=entry["manifest"], data=entry["data"])


def prepare(plan_path, bundle_manifest_path, output):
    """Bundle manifest: tasks[task_id].files[file] -> sealed source-bundle ref."""
    plan_path, bundle_manifest_path, output = map(Path, (plan_path, bundle_manifest_path, output))
    plan = checked_plan(plan_path)
    bundles = read(bundle_manifest_path)
    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(version="prompt8d-token-views-v1", source_plan=ref(plan_path),
                    bundles=ref(bundle_manifest_path), tasks={}, training_count=0)
    for task_id, item in bundles["tasks"].items():
        task = plan["tasks"][task_id]
        if task["record"]["task"] != "node":
            raise ValueError("B/C intervention is restricted to node tasks")
        info = read(checked_ref(task["prepared"]["0/1"]))
        graph = read_graph(checked_ref(info["profiles"]["G0"]["graph"]))
        encoder = TokenEncoder(task["record"]["feature"])
        by_file = {}
        for n, attrs in graph.nodes(data=True):
            by_file.setdefault(attrs["source_file"], []).append((n, attrs))
        files = {}
        for file, bundle_ref in item["files"].items():
            bundle = read(checked_ref(bundle_ref))
            source_ref = task["record"]["sources"][file]
            checked_ref(source_ref)
            if bundle["source_sha256"] != source_ref["sha256"]:
                raise ValueError("Renaming bundle source differs")
            files[file] = bundle
        views = {}
        for mode in MODES:
            rows, vectors, mappings = [], [], {}
            for file in sorted(by_file):
                mapping = files[file]["views"][mode]["mapping"] if file in files else {}
                mappings[file] = mapping
                audit = {r["node_identity"]: r for r in files[file]["views"][mode]["nodes"]} if file in files else {}
                if file in files and set(audit) != {n for n, _ in by_file[file]}:
                    raise ValueError("Renaming audit node population differs")
                for n, attrs in by_file[file]:
                    code = attrs["code"]
                    changed, edits = rewrite_node(code, mapping)
                    if file in files:
                        proof = audit[n]
                        if (proof["before_code_sha256"] != hashlib.sha256(code.encode()).hexdigest()
                                or proof["after_code_sha256"] != hashlib.sha256(changed.encode()).hexdigest()
                                or proof["before_length"] != proof["after_length"]):
                            raise ValueError("Source bundle code/token proof differs")
                    if not edits:
                        continue
                    before = encoder(code)
                    frozen = np.asarray(attrs["token"], dtype=np.float32)
                    if not np.array_equal(before, frozen):
                        raise ValueError("Reencoded original vector differs from frozen token")
                    after = encoder(changed)
                    rows.append(dict(file=file, original_graph_node_id=n,
                        source_sha256=task["record"]["sources"][file]["sha256"],
                        node_type=attrs["node_type"], vector_row=len(vectors),
                        code_before_sha256=proof["before_code_sha256"],
                        code_after_sha256=proof["after_code_sha256"],
                        original_vector_sha256=vector_sha256(before),
                        renamed_vector_sha256=vector_sha256(after),
                        before_token_length=proof["before_length"], after_token_length=proof["after_length"],
                        position_proof=proof["position_proof"], replacements=len(edits)))
                    vectors.append(after)
            dest = output / task_id / mode
            dest.mkdir(parents=True, exist_ok=False)
            data = dest / "vectors.npz"
            with data.open("xb") as stream:
                np.savez_compressed(stream, vectors=np.stack(vectors) if vectors else np.empty((0, 512), dtype=np.float32))
            report = dict(task_id=task_id, mode=mode, rows=rows, mappings=mappings,
                tokenizer=encoder.provenance, source_refs=task["record"]["sources"],
                frozen_graph=info["profiles"]["G0"]["graph"],
                model_scope="only outer-test rows applied by worker; stored views cover all folds",
                full_token_lengths_preserved=True)
            write_new(dest / "view.json", report)
            views[mode] = dict(manifest=ref(dest / "view.json"), data=ref(data), changed_nodes=len(rows))
            print("%s %s rows=%d" % (task_id, mode, len(rows)), flush=True)
        manifest["tasks"][task_id] = dict(views=views)
    write_new(output / "manifest.json", manifest)
    write_new(output / "manifest.seal.json", dict(sha256=sha256(output / "manifest.json")))
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--plan", required=True)
    p.add_argument("--bundles", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    prepare(a.plan, a.bundles, a.out)
