import json, sys
sys.path.insert(0, sys.argv[1])
from slither import Slither
from compile_repair.toolchain import slither as T
path, solc, args = sys.argv[2], sys.argv[3], sys.argv[4]
try:
    sl = Slither(path, solc=solc, solc_args=args, solc_disable_warnings=True)
    a, b = T.node_facts(sl, [path]), T.contract_coverage(sl, [path])
    print(json.dumps({"f": path.rsplit("/",1)[1], "args": args, "d3": a["mapping_complete"] and b["complete"], "nodes": a["counts"]["nodes"]}))
except Exception as e:
    print(json.dumps({"f": path.rsplit("/",1)[1], "args": args, "error": type(e).__name__ + ": " + str(e).splitlines()[0][:150]}))
