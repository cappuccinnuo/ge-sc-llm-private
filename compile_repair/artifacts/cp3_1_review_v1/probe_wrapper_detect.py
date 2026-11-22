"""standard_json_input on the Trace example (path given) and hand-made positive/negative inputs.
Usage (repo root): python3 -I probe_wrapper_detect.py <repo> <trace file or -> <out.json>"""
import json, os, sys
repo, trace, out = sys.argv[1:4]
sys.path.insert(0, repo); os.chdir(repo)
from compile_repair.toolchain.project import standard_json_input
C = {
 "etherscan_double_brace": b'{{"language":"Solidity","sources":{"a.sol":{"content":"contract A{}"}},"settings":{"optimizer":{"enabled":false}}}}',
 "standard_json": b'{"language":"Solidity","sources":{"a.sol":{"content":"contract A{}"}}}',
 "etherscan_flat_map": b'{"a.sol":{"content":"contract A{}"},"b.sol":{"content":"contract B{}"}}',
 "leading_whitespace": b'\n  {"language":"Solidity","sources":{"a.sol":{"content":"x"}}}  \n',
 "utf8_bom": b'\xef\xbb\xbf{"language":"Solidity","sources":{"a.sol":{"content":"x"}}}',
 "solidity_source": b'pragma solidity ^0.5.0;\ncontract A {}\n',
 "abi_json": b'[{"type":"function","name":"f"}]',
 "yul_standard_json": b'{"language":"Yul","sources":{"a.yul":{"content":"{}"}}}',
 "sources_url_only": b'{"language":"Solidity","sources":{"a.sol":{"urls":["bzz://x"]}}}',
 "empty_sources": b'{"language":"Solidity","sources":{}}',
 "truncated_json": b'{"language":"Solidity","sources":{"a.sol":{"content":"x"',
 "nan_constant": b'{"a.sol":{"content":"x"},"n":NaN}',
}
if trace != "-":
    C["trace_cp3_23864"] = open(trace, "rb").read()
res = {k: standard_json_input(v) for k, v in C.items()}
res = {k: (None if v is None else {"source_count": v["source_count"], "settings_keys": v["settings_keys"]}) for k, v in res.items()}
json.dump(res, open(out, "w"), indent=1)
for k, v in res.items(): print(f"{k:24} {v}")
