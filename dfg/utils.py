"""Small shared helpers: canonical JSON digest, tensor digest, seeding, metrics."""
import hashlib
import json
import random


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def tensor_digest(state):
    """SHA-256 over a state dict's names, dtypes, shapes and bytes (sorted by name)."""
    h = hashlib.sha256()
    for key, value in sorted(state.items()):
        value = value.detach().cpu().contiguous()
        h.update(key.encode())
        h.update(str(value.dtype).encode())
        h.update(str(tuple(value.shape)).encode())
        h.update(value.numpy().tobytes())
    return h.hexdigest()


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


def metrics(y, pred):
    """Binary scores in percent; ``buggy_f1`` is the F1 of the vulnerable class."""
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
