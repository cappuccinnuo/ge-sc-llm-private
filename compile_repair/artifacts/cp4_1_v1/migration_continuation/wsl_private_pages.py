"""Request transparent huge pages on one small private allocation, then immediately return them."""
import ctypes
from datetime import datetime, timezone
import json
import mmap
import os
from pathlib import Path
import re
import time

DEST = Path(__file__).resolve().parent
THP = Path("/sys/kernel/mm/transparent_hugepage")


def memory():
    meminfo = {r.split(":")[0]:int(r.split()[1]) for r in Path("/proc/meminfo").read_text().splitlines()
               if r.startswith(("MemFree:", "MemAvailable:", "Cached:"))}
    free = {r.split()[3]:list(map(int,r.split()[4:])) for r in Path("/proc/buddyinfo").read_text().splitlines()}
    return dict(meminfo_kib=meminfo,free_blocks_by_order=free,
                order7_or_above={zone:sum(counts[7:]) for zone,counts in free.items()})


def private_huge_kib(address, length):
    in_range = False
    huge = 0
    for line in Path("/proc/self/smaps").read_text().splitlines():
        bounds = re.match(r"^([0-9a-f]+)-([0-9a-f]+) ",line)
        if bounds:
            lo,hi=(int(v,16) for v in bounds.groups())
            in_range = lo < address + length and address < hi
        elif in_range and line.startswith("AnonHugePages:"):
            huge += int(line.split()[1])
    return huge


def main():
    before = memory()
    stamp = datetime.now(timezone.utc).isoformat()
    huge = int((THP/"hpage_pmd_size").read_text())
    length = 8 * huge
    assert length <= 16*1024**2 and before["meminfo_kib"]["MemAvailable"] >= 256*1024
    start = time.monotonic()
    with mmap.mmap(-1,length+huge,flags=mmap.MAP_PRIVATE|mmap.MAP_ANONYMOUS) as region:
        base = ctypes.addressof(ctypes.c_char.from_buffer(region))
        offset = (-base) % huge
        region.madvise(mmap.MADV_HUGEPAGE,offset,length)
        for i in range(offset,offset+length,os.sysconf("SC_PAGE_SIZE")):
            region[i] = 1
        active = private_huge_kib(base+offset,length)
    after = memory()
    facts = dict(utc=stamp,uid=os.getuid(),before=before,after=after,requested_bytes=length,
                 own_anonymous_hugepage_kib_before_release=active,elapsed_seconds=round(time.monotonic()-start,3),
                 thp_policy=(THP/"enabled").read_text().strip(),defrag_policy=(THP/"defrag").read_text().strip(),
                 method="MADV_HUGEPAGE on private anonymous pages; closed mapping before measuring free blocks",
                 global_settings_modified=False,system_restarts=0)
    with (DEST/"wsl_private_pages.json").open("x",encoding="utf8") as fp:
        json.dump(facts,fp,indent=2);fp.write("\n")
    print("private huge pages released (KiB)",active,"before",before["order7_or_above"],"after",after["order7_or_above"])
if __name__=="__main__":main()
