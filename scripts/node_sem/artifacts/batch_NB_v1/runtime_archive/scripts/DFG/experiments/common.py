"""Small experiment-only IO/provenance helpers (Codex, 2026-10-12)."""
import hashlib
import json
import random
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    tmp.replace(path)


def new_output(path):
    path = Path(path).resolve()
    if ROOT not in path.parents:
        raise ValueError("New experiment output must be below " + str(ROOT))
    if path.exists():
        raise FileExistsError("Refusing to overwrite " + str(path))
    return path


def utc():
    return datetime.now(timezone.utc).isoformat()


def seed_all(seed):
    import numpy as np
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def tensor_digest(state):
    h = hashlib.sha256()
    for key, value in sorted(state.items()):
        h.update(key.encode())
        h.update(str(value.dtype).encode())
        h.update(str(tuple(value.shape)).encode())
        h.update(value.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def code_hashes():
    paths = list(ROOT.glob("*.py")) + list(ROOT.parent.glob("*.py"))
    paths += [REPO / p for p in [
        "sco_models/model_hgt.py", "sco_models/graph_utils.py",
        "scripts/encode_tokenizer_features.py"]]
    return {str(p.relative_to(REPO)): sha256(p) for p in sorted(paths)}


def metrics(y, pred):
    from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
    if not y:
        raise ValueError("No scored samples")
    return {
        "n": len(y), "positive": sum(y),
        "buggy_f1": float(f1_score(y, pred, zero_division=0) * 100),
        "macro_f1": float(f1_score(y, pred, labels=[0, 1], average="macro", zero_division=0) * 100),
        "precision": float(precision_score(y, pred, zero_division=0) * 100),
        "recall": float(recall_score(y, pred, zero_division=0) * 100),
        "tn_fp_fn_tp": confusion_matrix(y, pred, labels=[0, 1]).ravel().tolist(),
    }



def scheduler_metadata(state):
    """JSON view of this environment's OneCycle state (not a resume payload)."""
    return {key: {"callable": getattr(value, "__module__", "") + "." +
                  getattr(value, "__qualname__", type(value).__name__)}
            if callable(value) else value for key, value in state.items()}
