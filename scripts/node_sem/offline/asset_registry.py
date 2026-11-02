"""Local-only model asset registry. No network, torch or graph dependencies."""
import argparse
import hashlib
import json
from pathlib import Path

VERSION = "nodesem-offline-assets-v1"
FAMILIES = {
    "Salesforce/codet5p-110m-embedding": ("codet5p-110m-embedding", 256, "model_default", True),
    "microsoft/unixcoder-base": ("unixcoder-base", 768, "mean", False),
    "BAAI/bge-small-en-v1.5": ("bge-small-en-v1.5", 384, "future_teacher", True),
}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reference(path):
    return dict(path=str(Path(path).resolve()), sha256=sha(path))


def checked(ref):
    path = Path(ref["path"])
    if sha(path) != ref["sha256"]:
        raise ValueError("Asset/input SHA differs: " + str(path))
    return path


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def write(path, value):
    with Path(path).open("x", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def register(root, output):
    root, output = Path(root).resolve(), Path(output)
    index = read(root / "MODEL_MANIFEST.json")
    if {m["repo_id"] for m in index["models"]} != set(FAMILIES):
        raise ValueError("Model inventory differs")
    models = {}
    for item in index["models"]:
        name, dim, pooling, normalized = FAMILIES[item["repo_id"]]
        folder = root / item["directory"]
        if folder.parent != root or folder.name != name:
            raise ValueError("Asset directory differs")
        source_ref = dict(path=str(folder / "download_manifest.json"),
                          sha256=item["manifest_sha256"])
        manifest = read(checked(source_ref))
        if (manifest["status"] != "complete" or manifest["revision"] != item["revision"]
                or (folder / "REVISION").read_text().strip() != item["revision"]):
            raise ValueError("Incomplete/unpinned model")
        files = {}
        for entry in manifest["files"]:
            path = folder / entry["path"]
            if folder not in path.resolve().parents:
                raise ValueError("Asset escapes local model directory")
            if path.stat().st_size != entry["bytes"] or sha(path) != entry["sha256"]:
                raise ValueError("Downloaded model file differs")
            files[entry["path"]] = dict(path=str(path), sha256=entry["sha256"])
        files["REVISION"] = reference(folder / "REVISION")
        files["download_manifest.json"] = source_ref
        identities = {key: value["sha256"] for key, value in files.items()}
        digest = hashlib.sha256(json.dumps(identities, sort_keys=True).encode()).hexdigest()
        models[name] = dict(repo_id=item["repo_id"], revision=item["revision"],
                           directory=str(folder), dimension=dim, pooling=pooling,
                           normalized=normalized, files=files, asset_sha256=digest)
    output.parent.mkdir(parents=True, exist_ok=True)
    result = dict(version=VERSION, models=models, source_index=reference(root / "MODEL_MANIFEST.json"),
                  local_files_only=True, network_used=False)
    write(output, result)
    write(output.with_suffix(".seal.json"), dict(assets=reference(output)))
    return result


def load_model_entry(path, name):
    path = Path(path)
    if read(path.with_suffix(".seal.json"))["assets"] != reference(path):
        raise ValueError("Assets seal differs")
    registry = read(path)
    if registry["version"] != VERSION:
        raise ValueError("Unknown assets version")
    entry = registry["models"][name]
    for ref in entry["files"].values():
        checked(ref)
    actual = hashlib.sha256(json.dumps(
        {k:v["sha256"] for k,v in entry["files"].items()},sort_keys=True).encode()).hexdigest()
    if actual != entry["asset_sha256"]:
        raise ValueError("Model asset digest differs")
    folder = Path(entry["directory"])
    allowed = {Path(r["path"]).resolve() for r in entry["files"].values()}
    for file in folder.rglob("*"):
        if file.is_file() and file.resolve() not in allowed:
            raise ValueError("Unregistered model file: " + str(file))
    return entry


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = register(args.root, args.out)
    print(json.dumps({k:dict(revision=v["revision"],asset_sha256=v["asset_sha256"])
                      for k,v in result["models"].items()}, indent=2))
