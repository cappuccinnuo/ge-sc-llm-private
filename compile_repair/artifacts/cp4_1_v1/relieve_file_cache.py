"""Release only clean cache pages from completed CP4 result/journal reads. File contents are read-only."""
import stat
import time
from batch import *

def memory():
    buddy=Path("/proc/buddyinfo").read_text().splitlines()
    return dict(buddyinfo=buddy,free_order7_or_larger={r.split()[3]:sum(map(int,r.split()[4:][7:])) for r in buddy},
                meminfo=[l for l in Path("/proc/meminfo").read_text().splitlines() if l.split(":")[0] in ("MemAvailable","MemFree","Cached")])

before=memory()
root=(LOCAL.parent/"cp4_v1/samples").resolve()
limit=2*1024**3
seen=set();advised=0;files=0;after=before
start=time.monotonic()
for obs in reversed(list(rows(OUT/"original_reclassified.jsonl.gz"))):
    for value in (Path(obs["result_path"]),Path(obs["mutation_path"]).with_name("invocations.jsonl")):
        p=value.resolve()
        if root not in p.parents or p in seen:continue
        seen.add(p)
        with p.open("rb") as fp:
            st=os.fstat(fp.fileno())
            if not stat.S_ISREG(st.st_mode) or st.st_size<32768:continue
            length=min(st.st_size,limit-advised)
            if length<=0:break
            os.posix_fadvise(fp.fileno(),0,length,os.POSIX_FADV_DONTNEED)
            files+=1;advised+=length
        if files%128==0:
            after=memory()
            if min(after["free_order7_or_larger"].values())>=32:break
    if advised>=limit or (files and min(after["free_order7_or_larger"].values())>=32):break
after=memory()
saved("runtime_cache_recovery.json",dict(before=before,after=after,files=files,advised_bytes=advised,
    cap_bytes=limit,scope=str(root),method="POSIX_FADV_DONTNEED on completed, read-only environment result and invocation journal file descriptors",
    elapsed_seconds=time.monotonic()-start,global_cache_drop=False,persistent_settings_changed=False))
print("read-only cache advice",files,advised,"before",before["free_order7_or_larger"],"after",after["free_order7_or_larger"])
