"""Advise the guest about clean pages of fully verified CP4.1 graph receipts after the final join."""
import json
import os
from pathlib import Path
import time
from wsl_private_pages import DEST, memory

with (DEST/"acceptance.json").open() as fp:
    acceptance=json.load(fp)
assert acceptance["complete"] and acceptance["packages"]["passed"]==114
root=(DEST.parents[4]/"compile-repair-local").resolve(strict=True)
seen=set()
before=memory()
start=time.monotonic()
total=0
for phase in acceptance["packages"]["phases"]:
    for line in (DEST/phase/"package_scores.jsonl").read_bytes().splitlines():
        row=json.loads(line)
        for mode in ("graph","migration_graph"):
            for field in ("graph_path","result_path","journal_path"):
                path=Path(row[mode][field]).resolve(strict=True)
                if path in seen:continue
                assert root in path.parents and path.is_file()
                with path.open("rb") as fp:
                    info=os.fstat(fp.fileno())
                    assert info.st_uid==os.getuid()
                    os.posix_fadvise(fp.fileno(),0,0,os.POSIX_FADV_DONTNEED)
                    total+=info.st_size
                seen.add(path)
report=dict(before=before,after=memory(),files_advised=len(seen),receipt_bytes_covered=total,
            source="114 completed packages, exact and migrated graph/result/journal only",
            elapsed_seconds=round(time.monotonic()-start,3),disk_files_changed=0,
            interpretation="Advisory operation; covered bytes are not a measurement of RAM reclaimed.")
with (DEST/"wsl_completed_receipts.json").open("x",encoding="utf8") as fp:
    json.dump(report,fp,indent=2);fp.write("\n")
print(len(seen),total,before["order7_or_above"],report["after"]["order7_or_above"])
