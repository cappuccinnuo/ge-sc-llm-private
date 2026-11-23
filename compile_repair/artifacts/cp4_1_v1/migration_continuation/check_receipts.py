"""Bind sealed Slither absolute input filenames to their recorded roots and source bytes."""
import json
from pathlib import Path
import sys

DEST = Path(__file__).resolve().parent
sys.path.insert(0,str(DEST.parent))
from batch import HERE, OLD, checked, rows, sha
from replay import restore_sample
from compile_repair.evaluation.benchmark import base_contents


def verify_files(project, source):
    root = Path(project["root"]).resolve(strict=True)
    digests = {}
    for item in project["files"]:
        path = (root / item["path"]).resolve(strict=True)
        name = path.relative_to(root).as_posix()
        if name in digests:
            raise ValueError("Duplicate physical project input")
        checked(path, item["sha256"])
        digests[name] = item["sha256"]
    if digests != {name:sha(data) for name,data in source.items()}:
        raise ValueError("Physical project input differs from the reconstructed closure")
    return len(digests)


def main():
    old = json.loads((HERE/"migration_stop_inventory.json").read_bytes())
    path = HERE/"migration_stop_receipts.jsonl.gz"
    checked(path, old["sha256"])
    receipts = [i for i in rows(path) if i.get("migration")]
    base = {i["unit_id"]:i for i in rows(OLD/"bases.jsonl.gz")}
    observations = {i["unit_id"]:i for stage in ("new","supplement") for i in rows(HERE/(stage+"_observations.jsonl.gz"))
                    if i["operator"]=="unresolved_package_import"}
    details = []
    for item in receipts:
        uid = item["unit_id"]
        sources = base_contents(base[uid])
        for mode in ("exact","migration"):
            ref = item[mode]
            result = json.loads(checked(ref["result_path"],ref["result_sha256"]))
            checked(ref["graph_path"],ref["graph_sha256"])
            project = result["attempts"][-1]["slither"]["project"]
            _, _, expected, _, _ = restore_sample(base[uid], sources, observations[uid], migration=(mode=="migration"))
            assert all(Path(row["path"]).is_absolute() for row in project["files"])
            count = verify_files(project, expected)
            details.append(dict(unit_id=uid,mode=mode,files=count,result_sha256=ref["result_sha256"]))
    assert len(receipts)==9 and len(details)==18
    raw_stop = (DEST/"stop.json").read_bytes()
    assert json.loads(raw_stop)["stop"]=="AssertionError" and (DEST/"package_scores.jsonl").stat().st_size==0
    with (DEST/"initial_receipt_check.json").open("x",encoding="utf8") as fp:
        json.dump(dict(scope="read-only path and SHA check of all sealed graph inputs",graphs=len(details),
                       receipts=details,first_stop_sha256=sha(raw_stop),
                       reason="Initial runner compared absolute native paths directly with project-relative sample keys.",
                       completed_scoring_rows_in_first_run=0,new_compiler_invocations_in_first_run=0,
                       checks="resolve each path beneath its recorded root; reject escaping paths or duplicate keys; compare actual bytes and the complete closure"),fp,indent=2)
        fp.write("\n")
    print("verified",len(details),"archived closures,",sum(i["files"] for i in details),"input-file receipts")
if __name__=="__main__":main()
