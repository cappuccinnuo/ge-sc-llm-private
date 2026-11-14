"""PROMPTS 3.8/4.3: exclusive artifacts, append-only journals and SHA256 seals."""
import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path


def sha256(path):
    """Hash a local file; propagate IO failures rather than invent an identity."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_checked_json(path, expected):
    """Verify a frozen identity before decoding JSON; raise on mismatched bytes."""
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Evidence SHA256 mismatch: " + str(path))
    return json.loads(raw.decode("utf8"))


def json_default(value):
    """Serialize records losslessly; byte edits use explicit hexadecimal encoding."""
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, bytes):
        return {"encoding": "hex", "data": value.hex()}
    if isinstance(value, Path):
        return str(value)
    raise TypeError("Unsupported artifact type: " + type(value).__name__)


class ArtifactStore:
    """Own one NEW directory; never overwrite files or follow artifact symlinks."""

    def __init__(self, path):
        self.path = Path(path).absolute()
        self.path.mkdir(parents=True, exist_ok=False)
        self.sealed = False

    def _target(self, name):
        if self.sealed:
            raise ValueError("Artifact store is sealed")
        part = Path(name)
        if part.is_absolute() or not part.parts or any(x in ("..", ".") for x in part.parts):
            raise ValueError("Artifact path must stay inside the store")
        target = self.path / part
        if any(p.is_symlink() for p in [target] + list(target.parents)):
            raise ValueError("Symlinks are not allowed in the artifact path")
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def write_bytes(self, name, data):
        """Exclusively write bytes within this store; return the absolute path."""
        target = self._target(name)
        with target.open("xb") as stream:
            stream.write(data)
        return target

    def write_json(self, name, value):
        """Exclusively write UTF-8 JSON; support data records and byte patches."""
        raw = json.dumps(value, default=json_default, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        return self.write_bytes(name, raw.encode("utf8"))

    def journal(self, name):
        """Create one flushed JSONL journal; caller owns the returned stream."""
        return self._target(name).open("x", encoding="utf8", newline="\n")

    def seal(self, tools, commit, implementation=None):
        """Seal all artifact bytes except seal itself; bind tools and actual code."""
        files = {}
        for path in sorted(self.path.rglob("*")):
            if path.is_symlink():
                raise ValueError("Cannot seal a symlink")
            if path.is_file():
                files[path.relative_to(self.path).as_posix()] = sha256(path)
        result = {"schema": "compile-repair-seal-v1", "files": files, "tools": tools,
                  "code_commit": commit, "implementation_sha256": implementation or {},
                  "llm_model": None, "llm_cache_index": None, "cost_usd": 0.0}
        self.write_json("seal.json", result)
        self.sealed = True
        return result


def emit(stream, item):
    """Append and flush one complete invocation or manifest record."""
    stream.write(json.dumps(item, default=json_default, ensure_ascii=False, sort_keys=True) + "\n")
    stream.flush()
