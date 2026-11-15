import hashlib, json, os, sys
repo, path, solc, n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
sys.path.insert(0, repo)
from slither import Slither
from compile_repair.toolchain import slither as T
for i in range(n):
    sl = Slither(path, solc=solc, solc_disable_warnings=True)
    nf = T.node_facts(sl, [path])
    g = T.graph_facts(sl) if hasattr(T, "graph_facts") else None
    writes = []
    for c in sl.contracts:
        for f in c.functions_and_modifiers:
            if f.name == "_combineMultiHash":
                for nd in f.nodes:
                    if nd.source_mapping.start == 5154:
                        writes.append((c.name, sorted(v.name for v in nd.local_variables_written)))
    print(json.dumps({"run": i + 1, "node_facts": hashlib.sha256(json.dumps(nf["nodes"], sort_keys=True).encode()).hexdigest()[:12],
                      "graph": hashlib.sha256(json.dumps(g, sort_keys=True, default=str).encode()).hexdigest()[:12] if g is not None else None,
                      "loop_cond_local_writes": writes}))
