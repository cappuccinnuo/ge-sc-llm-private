"""Check Codex's D18 request (59 compilers) against the official solc-bin linux-amd64 list.json.
Source used in review: https://raw.githubusercontent.com/ethereum/solc-bin/gh-pages/linux-amd64/list.json
(binaries.soliditylang.org itself was not reachable from the review environment).
Usage: python check_install_request.py <list.json> <compiler_installation_request.json>"""
import json, sys
gh, req = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))["compilers"]
V = lambda s: tuple(map(int, s.split(".")))
b = {x["version"]: x for x in gh["builds"] if "prerelease" not in x}
rel = [v for v in gh["releases"] if (0, 4, 12) <= V(v) <= V(gh["latestRelease"])]
strip = lambda h: h[2:] if h.startswith("0x") else h
bad = []
for v, e in req.items():
    g = b.get(v)
    if g is None:
        bad.append([v, "absent"]); continue
    for k in ("sha256", "keccak256"):
        if e[k] != strip(g[k]): bad.append([v, k])
    if not e["url"].endswith(g["path"]): bad.append([v, "url"])
print(json.dumps({"latest_release": gh["latestRelease"], "releases_in_support_range": len(rel),
                  "requested": len(req), "requested_outside_range": [v for v in req if v not in rel],
                  "implied_already_installed": sorted(set(rel) - set(req), key=V),
                  "mismatches": bad}, indent=1))
