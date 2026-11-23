"""Release only resident clean pages of this project's completed, read-only historical graph receipts."""
import ctypes
import gzip
import json
import mmap
import os
from pathlib import Path
import stat
import time

from wsl_private_pages import DEST, memory

PAGE = os.sysconf("SC_PAGE_SIZE")
CAP = 1024**3


def records(path):
    with gzip.open(path, "rt", encoding="utf8") as fp:
        for line in fp:
            yield json.loads(line)


def paths(batch):
    for r in records(batch/"retained_scores.jsonl.gz"):
        yield Path(r["graph"]["graph_path"])
        yield Path(r["graph"]["result_path"])
    for base in records(batch.parent/"cp4_v1/bases.jsonl.gz"):
        yield Path(base["graph_path"])
        yield Path(base["result"]["result_path"])


def main():
    lib=ctypes.CDLL(None,use_errno=True)
    lib.mincore.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_ubyte)]
    before=memory()
    root=(DEST.parents[4]/"compile-repair-local").resolve(strict=True)
    start=time.monotonic()
    seen=set(); examined=advised=resident=0; current=before
    for path in paths(DEST.parent):
        if path in seen:continue
        seen.add(path)
        if root not in path.resolve(strict=True).parents:continue
        with path.open("rb") as fp:
            info=os.fstat(fp.fileno())
            if info.st_uid!=os.getuid() or not stat.S_ISREG(info.st_mode) or info.st_size<2*PAGE:continue
            size=min(info.st_size,CAP-resident)
            if not size:break
            examined+=1
            with mmap.mmap(fp.fileno(),size,flags=mmap.MAP_PRIVATE,prot=mmap.PROT_READ|mmap.PROT_WRITE) as region:
                point=ctypes.addressof(ctypes.c_char.from_buffer(region))
                vector=(ctypes.c_ubyte*((size+PAGE-1)//PAGE))()
                if lib.mincore(point,size,vector):
                    raise OSError(ctypes.get_errno(),"mincore")
                cached=sum(x&1 for x in vector)*PAGE
            if cached:
                os.posix_fadvise(fp.fileno(),0,size,os.POSIX_FADV_DONTNEED)
                advised+=1;resident+=min(size,cached)
        if examined%256==0:
            current=memory()
            units=sum(sum(n*(2**(i-7)) for i,n in enumerate(counts) if i>=7)
                      for counts in current["free_blocks_by_order"].values())
            if units>=64:break
        if resident>=CAP:break
    result=dict(before=before,after=memory(),limit_resident_bytes=CAP,resident_bytes_advised=resident,
                files_examined=examined,files_with_resident_pages=advised,elapsed_seconds=round(time.monotonic()-start,3),
                scope=str(root),source_indices=["cp4_1_v1/retained_scores.jsonl.gz","cp4_v1/bases.jsonl.gz"],
                file_bytes_modified=False,global_settings_modified=False)
    with (DEST/"wsl_resident_receipts.json").open("x",encoding="utf8") as fp:
        json.dump(result,fp,indent=2);fp.write("\n")
    print(advised,"resident receipt files,",resident,"bytes; free blocks before",before["order7_or_above"],
          "after",result["after"]["order7_or_above"])
if __name__=="__main__":main()
