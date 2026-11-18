"""Small shared helpers: canonical JSON digest, tensor digest, seeding, metrics."""
import hashlib
import json
import random
import time


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


class Timer:
    """Wall-clock seconds per named phase; pending CUDA work is synchronized at each mark,
    so GPU time is charged to the phase that queued it."""

    def __init__(self, seconds=None):
        self.seconds = dict(seconds or {})
        self._last = time.monotonic()

    def mark(self, name):
        import torch
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        now = time.monotonic()
        self.seconds[name] = round(self.seconds.get(name, 0.0) + now - self._last, 2)
        self._last = now
        return self

    def summary(self, epochs):
        fit = self.seconds.get("fit")
        out = dict(self.seconds)
        if fit is not None and epochs:
            out["per_epoch"] = round(fit / epochs, 2)
        return out

    def line(self, epochs):
        s = self.summary(epochs)
        return "    time: " + ", ".join("%s %.1fs" % (k, v) for k, v in s.items())

