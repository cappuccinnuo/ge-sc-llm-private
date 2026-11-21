"""Do cast/new references to same-named contracts in different files bind correctly in
production Slither, and does compile_repair's project binding gate notice?
Usage (production env, repo root): python -I probe_alias_cast.py <repo> <project dir> <solc> <out.json>"""
import json, os, sys
repo, root, solc, out = sys.argv[1:5]
sys.path.insert(0, repo); os.chdir(repo)
from slither import Slither
from slither.slithir.operations import HighLevelCall, NewContract
from compile_repair.toolchain.slither import project_bindings
root = os.path.abspath(root)
sl = Slither("Main.sol", solc=solc, solc_working_dir=root, solc_disable_warnings=True,
             solc_args="--allow-paths " + root)
rows = []
for c in sl.contracts:
    for f in c.functions:
        for n in f.nodes:
            for ir in n.irs:
                if isinstance(ir, HighLevelCall) and ir.function is not None:
                    rows.append({"function": f.name, "op": "HighLevelCall", "expression": str(n.expression),
                                 "target_file": os.path.basename(ir.function.source_mapping.filename.absolute)})
                if isinstance(ir, NewContract):
                    cn = ir.contract_created
                    rows.append({"function": f.name, "op": "NewContract", "expression": str(n.expression),
                                 "target_file": os.path.basename(cn.source_mapping.filename.absolute)})
ast_refs = []
for unit in sl.compilation_units:
    asts = unit.crytic_compile_compilation_unit.asts
    decl = {}
    def walk(v, fn):
        if isinstance(v, dict):
            if v.get("nodeType") == "ContractDefinition": decl[v["id"]] = os.path.basename(fn)
            for x in v.values(): walk(x, fn)
        elif isinstance(v, list):
            for x in v: walk(x, fn)
    for fn, t in asts.items(): walk(t, fn)
    def refs(v):
        if isinstance(v, dict):
            if v.get("nodeType") in ("Identifier", "UserDefinedTypeName", "IdentifierPath") and v.get("referencedDeclaration") in decl:
                ast_refs.append({"name": v.get("name"), "src": v.get("src"), "file": decl[v["referencedDeclaration"]]})
            for x in v.values(): refs(x)
        elif isinstance(v, list):
            for x in v: refs(x)
    refs(asts[[k for k in asts if k.endswith("Main.sol")][0]])
gate = project_bindings(sl, [os.path.join(root, p) for p in ("Main.sol", "A.sol", "B.sol")], root)
res = {"slither_targets": rows, "solc_ast_references_in_Main": ast_refs,
       "gate_complete": gate["complete"], "gate_checked": gate["checked"]}
json.dump(res, open(out, "w"), indent=1); print(json.dumps(res, indent=1))
