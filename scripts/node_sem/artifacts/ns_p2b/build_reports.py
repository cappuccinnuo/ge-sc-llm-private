"""Build corrected prose from immutable evidence; never changes experiment files."""
import hashlib
import json
from pathlib import Path
import re

from scripts.node_sem.doc_check import check

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
P2=OUT.parent/"ns_p2"
def read(p):return json.loads(Path(p).read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()
def table(headers,rows):
    return "\n".join(["| "+" | ".join(headers)+" |","| "+" | ".join(["---"]*len(headers))+" |"]+
        ["| "+" | ".join(map(str,row))+" |" for row in rows])
templates=read(OUT/"document_templates.json")
fields=read(OUT/"document_prose.json")
env=read(P2/"environment/environment.json")
scope=read(P2/"environment/installation_scope.json")
cleanup=read(P2/"environment/cleanup_completed.json")
oldtests=read(P2/"validation.json")
newtests=read(OUT/"tests.json")
text=read(P2/"text_acceptance.json")["tasks"]
encoded=read(P2/"acceptance.json")["manifest_records"]
numbering=read(OUT/"numbering_effect.json")["tasks"]
residual=read(OUT/"residual_names.json")["tasks"]
assets=read(ROOT/"scripts/node_sem/offline/assets.json")["models"]
tasks=list(text)
fields.update(env_python=env["python"].split()[0],env_torch=env["torch"],
    env_cuda=env["cuda"],env_transformers=env["transformers"],env_sentence=env["sentence_transformers"],
    restored_packages=", ".join(k+" "+v for k,v in scope["observed_side_effect"]["restored_exact_versions"].items()),
    cleanup_count=str(len(cleanup["files"])),cleanup_bytes=str(cleanup["bytes_removed"]),
    cleanup_models=str(cleanup["model_and_feature_files_removed"]),
    model_table=table(["model","revision"],[[v["repo_id"],v["revision"]] for v in assets.values()]),
    old_total=str(oldtests["unique_passed"]),
    row_counts="/".join(str(text[t]["views"]["original"]["rows"]) for t in tasks),
    single_rows=str(sum(text[t]["views"]["original"]["rows"] for t in tasks)),
    total_rows=str(sum(r["encoding"]["rows"] for r in encoded.values())),
    seconds="%.3f"%sum(r["encoding"]["elapsed_seconds"] for r in encoded.values()),
    peak="%.3f"%max(r["encoding"]["peak_allocated_bytes"]/2**20 for r in encoded.values()),
    peak_min="%.3f"%min(r["encoding"]["peak_allocated_bytes"]/2**20 for r in encoded.values()),
    original_truncated="/".join(str(encoded[t+"/original"]["encoding"]["truncated_rows"]) for t in tasks),
    anonymous_truncated="/".join(str(encoded[t+"/anonymous"]["encoding"]["truncated_rows"]) for t in tasks))
shape=[];enc=[]
for task in tasks:
    inv=text[task]["invariants"];m=text[task]["views"]["original"]["cut_modes"]
    shape.append([task,inv["original_nodes"],inv["auxiliary_nodes"],text[task]["views"]["original"]["rows"]]+
                 [m.get(k,0) for k in ["ast_header","full","ast_signature","ast_condition","placeholder","fallback"]])
    for view in ["original","anonymous"]:
        d=encoded[task+"/"+view]["encoding"]
        enc.append([task,view,d["rows"],d["unique_texts"],"%.3f"%(100*(1-d["unique_texts"]/d["rows"])),
                    d["truncated_rows"],"%.3f"%d["elapsed_seconds"],"%.3f"%(d["peak_allocated_bytes"]/2**20),
                    str(d["repeat_bitwise"]),d["repeat_max_abs_error"]])
fields["shape_table"]=table(["task","F0","env","F3","header","full","signature","condition","placeholder","fallback"],shape)
fields["encoding_table"]=table(["task","view","rows","unique","dedup %","truncated","seconds","peak MiB","bitwise","max error"],enc)
def tests_table(suites):
    return table(["suite","passed","failed","skipped","warnings","seconds"],
        [[n,d["passed"],d["failed"],d["skipped"],d["warnings"],"%.3f"%d["seconds"]] for n,d in suites.items()])
fields["old_tests_table"]=tests_table(oldtests["suites"])
fields["new_tests_table"]=tests_table(newtests["suites"])
fields["new_tests_summary"]="%d passed; %d failed; %d skipped; %d warnings."%(
    newtests["passed"],newtests["failed"],newtests["skipped"],sum(d["warnings"] for d in newtests["suites"].values()))
nr=[]
for task in tasks:
    d=numbering[task];w=d["within_pair_weighted"];c=d["control_same_type"]
    nr.append([task,str(d["split_statements"])+"/"+str(d["shared_statements"]),w["count"]]+
              ["%.6f"%x[k] for x in [w,c] for k in ["mean","median","p05"]])
fields["numbering_table"]=table(["task","split/shared","pairs","within mean","median","p05","control mean","median","p05"],nr)
fields["within_means"]="/".join("%.6f"%numbering[t]["within_pair_weighted"]["mean"] for t in tasks)
fields["control_means"]="/".join("%.6f"%numbering[t]["control_same_type"]["mean"] for t in tasks)
fields["residual_table"]=table(["task","checked statements","nonreserved code occurrences","marker matches","reserved identifier type groups"],
    [[t,residual[t]["checked_source_statement_rows"],residual[t]["nonreserved_code_occurrences"],
      len(residual[t]["marker_matches"]),len(residual[t]["retained_reserved_identifiers"])] for t in tasks])
def render(s):
    for _ in range(10):
        next_s=re.sub(r"\{([A-Za-z0-9_]+)\}",lambda m:fields.get(m.group(1),m.group(0)),s)
        if next_s==s:break
        s=next_s
    assert not re.search(r"\{[A-Za-z0-9_]+\}",s),s
    return s.replace("three historical sections","three historical sections (prefix/suffix checks)")
# Explicit reconstruction ranges and untouched prefix/suffix preservation.
records=read(OUT/"corrupted_docs/index.json")
results=[];append_offsets={}
keys=["p2_report","p2_progress","p2_handover","p2_changes"]
for record,key in zip(records,keys):
    p=ROOT/record["path"];current=p.read_bytes()
    assert sha(current)==record["current_sha256"]
    replacement=render(templates[key]).encode("utf8")
    if record["start_byte"]==0:
        assert record["path"].endswith("NS_P2_REPORT.md")
        new=replacement
    else:
        start,end=record["start_byte"],record["end_byte_exclusive"]
        assert current[start:end]==Path(record["archive_path"]).read_bytes()
        new=current[:start]+replacement+current[end:]
        assert new[:start]==current[:start]
        assert new[start+len(replacement):]==current[end:]
    p.write_bytes(new)
    append_offsets[record["path"]]=len(new)
    results.append(dict(path=record["path"],original_archive=record["archive_path"],
        before_sha256=sha(current),replacement_start_byte=record["start_byte"],
        replacement_bytes=len(replacement),after_replacement_sha256=sha(new),
        prefix_sha256=record["prefix_sha256"],
        prefix_unchanged=(record["start_byte"]!=0),
        suffix_sha256=record["suffix_sha256"],
        suffix_unchanged=(record["start_byte"]!=0),preexisting_suffix_bytes=record["suffix_bytes"],
        doc_check=check(p,expect_cjk=True)))
for key,path in [("p2b_progress","scripts/node_sem/PROGRESS.md"),("p2b_handover","HANDOVER.md"),
                 ("p2b_changes","docs/training_changes_2026-10-07.md")]:
    p=ROOT/path
    with p.open("ab") as f:f.write(("\n\n"+render(templates[key])).encode("utf8"))
    check(p,append_offsets[path],expect_cjk=True)
report=ROOT/"scripts/node_sem/NS_P2B_REPORT.md"
with report.open("x",encoding="utf8",newline="\n") as f:f.write(render(templates["p2b_report"]))
check(report,expect_cjk=True)
with (OUT/"document_rewrite.json").open("x",encoding="utf8") as f:
    json.dump(dict(source_archive_commit="f049d18e",replacements=results,
        append_offsets=append_offsets,rendered_numeric_fields=fields,approved_suffix_preserved=True),f,ensure_ascii=True,indent=2)
print("Corrected four documents, preserved both sides of each replaced section, appended NS-P2b records.")
