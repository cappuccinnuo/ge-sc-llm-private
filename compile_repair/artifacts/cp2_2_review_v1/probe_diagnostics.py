"""What solc reports for erroneous sources: CLI stderr (combined-json, as the module compiles)
and standard JSON (type, errorCode, sourceLocation). Usage: python3 -I probe_diagnostics.py <solc dir> <out.json> <file> ..."""
import json, os, subprocess, sys
solc_dir, out, files = sys.argv[1], sys.argv[2], sys.argv[3:]
VERSIONS = ["0.4.12", "0.4.17", "0.4.24", "0.4.26", "0.5.0", "0.5.17", "0.6.0", "0.6.12", "0.7.6", "0.8.0", "0.8.38"]
rows = []
for f in files:
    src = open(f, encoding="utf8").read()
    for v in VERSIONS:
        b = os.path.join(solc_dir, "solc-" + v)
        if not os.path.exists(b):
            continue
        cli = subprocess.run([b, "--combined-json", "abi", os.path.basename(f)], cwd=os.path.dirname(f) or ".",
                             capture_output=True, text=True)
        sj_in = {"language": "Solidity", "sources": {os.path.basename(f): {"content": src}},
                 "settings": {"outputSelection": {"*": {"*": ["evm.bytecode.object"]}}}}
        sj = subprocess.run([b, "--standard-json"], input=json.dumps(sj_in), capture_output=True, text=True)
        try:
            errs = [{k: e.get(k) for k in ("type", "errorCode", "sourceLocation", "message")}
                    for e in json.loads(sj.stdout).get("errors", []) if e.get("severity") == "error"]
        except ValueError:
            errs = [{"unparsable_stdout": sj.stdout[:200]}]
        heads = [l for l in cli.stderr.splitlines() if "Error" in l.split(":", 3)[-2:][0] or l.startswith(("Error", " -->")) or ": Error:" in l]
        rows.append({"file": os.path.basename(f), "version": v, "cli_rc": cli.returncode,
                     "cli_error_lines": heads[:6], "standard_json_errors": errs})
        print(json.dumps(rows[-1])[:400], flush=True)
json.dump(rows, open(out, "w"), indent=1)
