"""Recover the exact archived combined JSON for the two authorized Yul projects only."""
import json
from pathlib import Path
import subprocess
import sys
import time

DEST = Path(__file__).resolve().parent
sys.path.insert(0, str(DEST.parent))
from resume_migrations import checked, sha
from batch import ROOT

SCRATCH = ROOT.parent/"compile-repair-local"/"cp4_1_v1"/"migration_continuation"/"yul_continuation"/"witnesses"


def save(path, value):
    with path.open("x", encoding="utf8") as fp:
        json.dump(value, fp, indent=2, ensure_ascii=False)
        fp.write("\n")


def witness(uid, side, ref):
    auth = json.loads((DEST/"authorization.json").read_bytes())
    assert uid in auth["allowed_units"] and side in ("truth","repaired")
    assert len(auth["allowed_units"])*2 == auth["max_extra_solc_calls"]
    result_bytes = checked(ref["result_path"],ref["result_sha256"])
    a = json.loads(result_bytes)["attempts"][-1]
    c, s = a["solc"], a["slither"]
    assert c["returncode"]==0 and s["d3"] and s["graph_sha256"]==ref["graph_sha256"]
    assert c["cwd"]==s["project"]["root"] and c["command"]==s["equivalent_solc_argv"]
    assert c["compiler"]["path"]==c["command"][0] and sha(Path(c["command"][0]).read_bytes())==s["compiler_sha256"]==c["compiler"]["sha256"]
    root = Path(c["cwd"]).resolve(strict=True)
    for item in s["project"]["files"]:
        path = Path(item["path"]).resolve(strict=True)
        path.relative_to(root)
        checked(path,item["sha256"])
    raw_dir=SCRATCH/uid/side
    log_dir=DEST/"witnesses"/uid/side
    log_dir.mkdir(parents=True,exist_ok=True)
    raw_dir.mkdir(parents=True,exist_ok=True)
    output=raw_dir/"combined.json"
    entry=log_dir/"invocation.json"
    done=log_dir/"verified.json"
    if not entry.exists():
        save(entry,dict(unit_id=uid,side=side,command=c["command"],cwd=str(root),
                        old_result_sha256=ref["result_sha256"],old_graph_sha256=ref["graph_sha256"],
                        expected_stdout_sha256=c["stdout_sha256"]))
        start=time.monotonic()
        with output.open("xb") as fp, (raw_dir/"stderr.txt").open("xb") as err:
            proc=subprocess.run(c["command"],cwd=root,stdout=fp,stderr=err,timeout=75,check=False)
        raw=output.read_bytes()
        save(log_dir/"observed.json",dict(returncode=proc.returncode,stdout_sha256=sha(raw),
             stderr_sha256=sha((raw_dir/"stderr.txt").read_bytes()),seconds=round(time.monotonic()-start,3)))
        assert proc.returncode==0 and sha(raw)==c["stdout_sha256"], "Original combined JSON was not reproduced"
        data=json.loads(raw)
        paths=dict(s["project"]["source_units"])
        recorded={Path(t["path"]).relative_to(root).as_posix():t["ast_sha256"] for t in s["contract_coverage"]["asts"]}
        ast_check={}
        for logical in data["sourceList"]:
            ast=data["sources"][logical]["AST"]
            physical=paths[logical]
            digest=sha(json.dumps(ast,sort_keys=True).encode("utf8"))
            assert digest==recorded[physical]
            ast_check[physical]=digest
        assert len(ast_check)==len(recorded) and set(ast_check)==set(recorded)
        save(done,dict(output_path=str(output),stdout_sha256=sha(raw),source_list=data["sourceList"],
                       physical_ast_sha256=ast_check,old_result_path=ref["result_path"],
                       old_result_sha256=ref["result_sha256"],old_graph_sha256=ref["graph_sha256"]))
    summary=json.loads(done.read_bytes())
    assert summary["old_result_sha256"]==ref["result_sha256"] and summary["old_graph_sha256"]==ref["graph_sha256"]
    return dict(combined_json=checked(output,c["stdout_sha256"]),result=json.loads(result_bytes))


if __name__=="__main__":
    stop=json.loads((DEST.parent/"tuple_continuation/stop.json").read_bytes())
    for side,key in (("truth","graph"),("repaired","migration_graph")):
        data=witness(stop["unit_id"],side,stop[key])
        print(side,len(data["combined_json"]),"bytes verified",flush=True)
