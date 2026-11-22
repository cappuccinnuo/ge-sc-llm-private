"""Seal numeric evidence, implementation, run logs, and the losslessly archived per-sample receipts."""
from batch import BASE, HERE, LOCAL, OUT, ROOT, checked, load, save, sha


def main():
    acceptance=load("acceptance.json")
    archives=load("archives.json")
    assert acceptance["passed"]
    for fname,ref in archives.items():
        checked(OUT/fname,ref["sha256"])
    raw={n[:-3] for n in archives}
    excluded={"seal.json","doc_check.json","doc_check.log"}
    artifacts={}
    for path in sorted(OUT.rglob("*")):
        if not path.is_file():continue
        name=path.relative_to(OUT).as_posix()
        if name in excluded or name in raw or path.suffix==".md" or "__pycache__" in path.parts:continue
        artifacts[name]=dict(sha256=sha(path.read_bytes()),bytes=path.stat().st_size)
    scripts={p.name:sha(p.read_bytes()) for p in sorted(HERE.glob("*.py"))}
    controls=load("control_acceptance.json")
    checked(controls["external_seal_path"],controls["external_seal_sha256"])
    save("seal.json",dict(schema="compile_repair.cp4_evidence.v1",base_commit=BASE,passed=True,
        artifacts=artifacts,scripts=scripts,implementation=acceptance["scope"]["production_sha256"],
        external_root=str(LOCAL),external_controls_seal=dict(path=controls["external_seal_path"],sha256=controls["external_seal_sha256"]),
        external_per_sample_sources="sample_receipts.jsonl.gz pins each mutation, result and journal; mutation pins all file bytes",
        original_streams={name:row["uncompressed_sha256"] for name,row in archives.items()},
        document_check="doc_check.json separately records the post-seal document check"))
    print(sha((OUT/"seal.json").read_bytes()))


if __name__=="__main__":
    main()
