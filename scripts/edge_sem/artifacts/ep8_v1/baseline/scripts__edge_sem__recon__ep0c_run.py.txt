"""EP0c CPU command receipt; adapted from ep0b_run, no automatic retries."""
import argparse
import os
import subprocess
import sys
import time
from .ep0c_common import OUT
from .common import ref, write


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("args", nargs=argparse.REMAINDER)
    args = p.parse_args()
    if not (OUT/"before.json").is_file():
        raise ValueError("Prepare EP0c first")
    argv = args.args[1:] if args.args and args.args[0] == "--" else args.args
    if not argv:
        raise ValueError("Missing command")
    command = [sys.executable, "-B"] + argv
    dest = OUT/"execution"
    write(dest/(args.name+".started.json"), dict(
        command=command, started=time.time(), CUDA_VISIBLE_DEVICES=os.environ.get("CUDA_VISIBLE_DEVICES")))
    start = time.monotonic()
    with (dest/(args.name+".log")).open("x", encoding="utf8") as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    write(dest/(args.name+".json"), dict(command=command, exit_code=result.returncode,
          seconds=time.monotonic()-start, log=ref(dest/(args.name+".log"))))
    print(args.name, "exit", result.returncode, flush=True)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
