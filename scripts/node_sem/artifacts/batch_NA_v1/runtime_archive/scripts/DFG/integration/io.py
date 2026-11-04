"""Checksummed source identities and non-overwriting graph bundles."""
import json
import hashlib
from pathlib import Path
from scripts.labeling_v2.safe_graph import read_graph, write_graph
from ..graph_audit import fingerprint
from . import VERSION
from .pipeline import computation_fingerprint


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(1024*1024), b""):
            h.update(data)
    return h.hexdigest()


def checked(path, expected):
    path = Path(path).resolve()
    if not expected or sha256(path) != expected:
        raise ValueError("Missing/mismatched SHA256: " + str(path))
    return path


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def read_sources(path, graph):
    path = Path(path).resolve()
    doc = read_json(path)
    records = doc.get("sources", doc)
    if not isinstance(records, dict):
        raise ValueError("Source manifest requires a mapping")
    sources, metadata, used, missing = {}, {}, {}, []
    for name in sorted({d["source_file"] for _,d in graph.nodes(data=True)}):
        if name not in records:
            missing.append(name)
            continue
        rec = records[name]
        if not isinstance(rec, dict) or "path" not in rec:
            raise ValueError("Source requires path and sha256")
        p = checked(path.parent / rec["path"], rec.get("sha256"))
        sources[name] = p.read_bytes().decode("utf8")
        metadata[name] = rec.get("metadata")
        used[name] = dict(rec, path=str(p))
    return sources, metadata, used, missing


def write_bundle(output, graph, audit, inputs):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Refusing to overwrite " + str(output))
    json.dumps(audit, ensure_ascii=False)
    json.dumps(inputs, ensure_ascii=False)
    output.mkdir(parents=True)
    path = output / "hcg.gpickle"
    write_graph(graph, path)
    if fingerprint(read_graph(path)) != fingerprint(graph):
        raise AssertionError("Graph serialization failed roundtrip")
    write_json(output / "audit.json", audit)
    write_json(output / "inputs.json", inputs)
    result = {"version": VERSION, "profile": audit["profile"],
              "adapter": "scripts.DFG.integration.model.make_model",
              "graph": {"path": str(path), "sha256": sha256(path),
                "fingerprint": fingerprint(graph),
                "computation_fingerprint": computation_fingerprint(graph)},
              "audit_sha256": sha256(output / "audit.json"),
              "inputs_sha256": sha256(output / "inputs.json"),
              "nodes": len(graph), "edges": graph.number_of_edges(), "training_executed": False}
    write_json(output / "manifest.json", result)
    return result
