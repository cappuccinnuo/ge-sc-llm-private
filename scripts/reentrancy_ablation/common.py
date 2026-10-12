"""Codex 2026-10-08: isolated, audited reentrancy ablations."""
import os, sys, json, hashlib, random
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for directory in [REPO, REPO / "scripts/labeling_v2"]:
    sys.path.insert(0, str(directory))
from safe_graph import read_graph, write_graph, sha256
from label_rules import align_graphs, parse_records

def utc():
    return datetime.now(timezone.utc).isoformat()

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf8"))

def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf8")
    temp.replace(path)

def confined(path):
    path = Path(path).resolve()
    if HERE not in path.parents:
        raise ValueError("All outputs must remain inside " + str(HERE))
    return path

def snapshot_originals():
    result = {}
    for p in REPO.rglob("*"):
        if p.is_file() and p.suffix in {".py", ".sh", ".md"} and HERE not in p.parents:
            if any(s in p.parts for s in [".git", "__pycache__", "node_modules", ".venv"]):
                continue
            result[str(p)] = sha256(p)
    return result

def object_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def graph_digests(graph):
    import numpy as np
    ids = list(graph.nodes())
    features = hashlib.sha256()
    for n in ids:
        arr = np.asarray(graph.nodes[n]["token"], dtype=np.float32)
        if arr.shape != (512,) or not np.isfinite(arr).all():
            raise ValueError("Bad feature at " + str(n))
        features.update(arr.tobytes())
    endpoints = sorted(Counter((int(s), int(t)) for s,t in graph.edges()).items())
    typed = sorted(Counter((int(s), int(t), d["edge_type"]) for s,t,d in graph.edges(data=True)).items())
    return {"nodes": len(ids), "edges": graph.number_of_edges(),
            "files": len({d["source_file"] for _,d in graph.nodes(data=True)}),
            "positive_nodes": sum(bool(parse_records(d.get("node_info_vulnerabilities"))) for _,d in graph.nodes(data=True)),
            "edge_types": dict(Counter(d["edge_type"] for _,_,d in graph.edges(data=True))),
            "identities": object_hash([(n,graph.nodes[n]["source_file"],graph.nodes[n]["node_type"],graph.nodes[n].get("code")) for n in ids]),
            "endpoints": object_hash(endpoints), "typed_edges": object_hash(typed),
            "labels": object_hash([int(bool(parse_records(graph.nodes[n].get("node_info_vulnerabilities")))) for n in ids]),
            "features": features.hexdigest()}

def seed_all(seed):
    import numpy as np, torch
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True

def tensor_digest(state):
    h = hashlib.sha256()
    for name,tensor in sorted(state.items()):
        h.update(name.encode()); h.update(str(tuple(tensor.shape)).encode())
        h.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()

def metrics(y, pred):
    import numpy as np
    from sklearn.metrics import f1_score, confusion_matrix
    y = np.asarray(y, dtype=int); pred = np.asarray(pred, dtype=int)
    if not len(y):
        return None
    return {"n":len(y), "positive":int(y.sum()),
            "buggy_f1":float(f1_score(y,pred,average="binary",zero_division=0)*100),
            "macro_f1":float(f1_score(y,pred,average="macro",labels=[0,1],zero_division=0)*100),
            "tn_fp_fn_tp":confusion_matrix(y,pred,labels=[0,1]).ravel().tolist()}
