"""Fetch official linux-amd64 solc builds from ethereum/solc-bin and verify SHA256 against the saved official index."""
import hashlib, json, os, sys, urllib.request
need = json.load(open(sys.argv[1])); index = json.load(open(sys.argv[2])); out = sys.argv[3]
paths = {b["version"]: "https://raw.githubusercontent.com/ethereum/solc-bin/gh-pages/linux-amd64/" + b["path"].replace("+", "%2B") for b in index["builds"]}
# Pre-0.4.10 builds are not in the official linux-amd64 index; solc-select takes them from crytic/solc.
for b in json.load(open(sys.argv[4]))["builds"]:
    paths.setdefault(b["version"], "https://raw.githubusercontent.com/crytic/solc/master/linux/amd64/" + b["name"])
done = []
for v, sha in sorted(need.items()):
    dst = os.path.join(out, "solc-" + v)
    if os.path.exists(dst) and hashlib.sha256(open(dst, "rb").read()).hexdigest() == sha:
        done.append(v); continue
    url = paths[v]
    data = urllib.request.urlopen(url, timeout=300).read()
    got = hashlib.sha256(data).hexdigest()
    if got != sha:
        sys.exit("SHA mismatch " + v)
    open(dst, "wb").write(data); os.chmod(dst, 0o755); done.append(v)
print(len(done), "verified")
