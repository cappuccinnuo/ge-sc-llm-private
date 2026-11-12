"""Bounded CPU command wrapper for EP0b, preserving every attempt without retries."""
import argparse
import os
import subprocess
import sys
import time
from .ep0b_common import OUT
from .common import ref, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    dest = OUT/"execution"
    if not OUT.is_dir():
        raise ValueError("Prepare EP0b first")
    command_args = args.args[1:] if args.args and args.args[0] == "--" else args.args
    if not command_args:
        raise ValueError("Missing command")
    command = [sys.executable, "-B"] + command_args
    write(dest/(args.name+".started.json"), dict(command=command, started=time.time(),
          CUDA_VISIBLE_DEVICES=os.environ.get("CUDA_VISIBLE_DEVICES")))
    start = time.monotonic()
    with (dest/(args.name+".log")).open("x", encoding="utf8") as log:
        run = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    write(dest/(args.name+".json"), dict(command=command, exit_code=run.returncode,
          seconds=time.monotonic()-start, log=ref(dest/(args.name+".log"))))
    print(args.name, "exit", run.returncode, flush=True)
    sys.exit(run.returncode)


if __name__ == "__main__":
    main()
