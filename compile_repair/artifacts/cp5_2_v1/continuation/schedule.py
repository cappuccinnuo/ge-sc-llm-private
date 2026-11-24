"""Run disjoint measurements with bounded concurrency; stop dispatch at the first nonzero result."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from stage import OUT, ROOT, write

tasks = [
    ("development_partial_ir","measure","ir","real_dev"),
    ("external_part0","measure","real","0","4"),
    ("v2_move","moved_v2"),
    ("external_part1","measure","real","1","4"),
    ("bench_partial_ir","measure","ir","benchmark"),
    ("all_benchmarks","benchmarks","rerun"),
    ("external_part2","measure","real","2","4"),
    ("base_partial_ir","measure","ir","cp3"),
    ("external_part3","measure","real","3","4"),
]
write(OUT/"schedule_start.json",dict(tasks=tasks,workers=4,pid=os.getpid(),python=sys.executable,
    cwd=str(ROOT),freeze=str(OUT.parent/"frozen_suites/source_freeze.json")))
running = {}
with (OUT/"schedule.log").open("x",encoding="utf8") as log:
    while tasks or running:
        for name, process in list(running.items()):
            rc = process.poll()
            if rc is not None:
                print(name,rc,file=log,flush=True)
                del running[name]
                if rc:
                    tasks.clear()
        if (OUT/"measurement_stop.json").exists():
            tasks.clear()
        while len(running)<4 and tasks:
            task=tasks.pop(0)
            print("start",task,file=log,flush=True)
            running[task[0]]=subprocess.Popen([sys.executable,"-B",str(OUT/"stage.py"),*task],cwd=ROOT,
                                               stdout=log,stderr=subprocess.STDOUT)
        if running:
            time.sleep(5)
sys.exit(1 if (OUT/"measurement_stop.json").exists() else 0)
