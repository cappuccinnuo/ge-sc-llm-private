"""Describe (without copying content) a .sol corpus entry that is an Etherscan
standard-JSON input wrapper. Usage: python3 -I inspect_wrapper.py <file> <out.json>"""
import hashlib, json, sys
path, out = sys.argv[1:3]
raw = open(path, "rb").read()
text = raw.decode("utf8").strip()
double = text.startswith("{{") and text.endswith("}}")
data = json.loads(text[1:-1] if double else text)
res = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "double_brace": double,
       "top_level_keys": sorted(data), "language": data.get("language"),
       "settings_keys": sorted(data.get("settings", {})),
       "optimizer": data.get("settings", {}).get("optimizer"),
       "evmVersion": data.get("settings", {}).get("evmVersion"),
       "source_count": len(data.get("sources", {})),
       "source_names": sorted(data.get("sources", {}))}
json.dump(res, open(out, "w"), indent=1); print(json.dumps(res)[:900])
