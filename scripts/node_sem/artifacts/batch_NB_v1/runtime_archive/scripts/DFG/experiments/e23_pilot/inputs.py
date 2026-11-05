"""Read-only provenance: frozen Stage C files/folds/config + D1 E2 + Stage F E3."""
import copy
from pathlib import Path
from collections import Counter
import numpy as np
from scripts.DFG.experiments.common import read_json,sha256,digest,write_json
from scripts.DFG.experiments.paper_protocol import validate_document
from scripts.DFG.experiments.runtime import assert_disconnected_files
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.graph_audit import fingerprint,frozen
from scripts.DFG.state.stage_f.projection import assert_preserved
from . import VARIANTS
ROOT=Path(__file__).resolve().parents[4]
ORIGINAL=ROOT.with_name("ge-sc-llm")
OLD_RUN=ORIGINAL/"scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c"
STAGE_F=ROOT/"scripts/DFG/experiments/audit/state_aware_ddg_stage_f"
DEFAULT_OUTPUT=ROOT/"scripts/DFG/experiments/artifacts/paper_kfold/e23_pilot_v1"
TASK_ORDER=("reentrancy_author_contract","access_control_author_contract","reentrancy_author_node","access_control_author_node")
EXPECTED={TASK_ORDER[0]:(6,847,547),TASK_ORDER[1]:(11,33,0),TASK_ORDER[2]:(3,829,547),TASK_ORDER[3]:(4,16,0)}
RELATIONS=("STATE_DEF_USE","STATE_ACCESS_ORDER","EXTERNAL_CALL_BEFORE_STATE_WRITE")
NUMERIC_KEYS=("seed","schedule_epochs","hidden_size","layers","heads","use_norm","dropout","feature",
"optimizer","initial_lr","max_lr","div_factor","final_div_factor","cycle_momentum","weight_decay",
"loss","patience","delta","selection","primary_checkpoint","secondary_checkpoint","batch",
"schema_policy","partition_policy","device","threads","metric_unit","protocol","protocol_version","forward_scope","score_role")
def check_hashes(records):
    for path,expected in records.items():
        if sha256(path)!=expected:raise ValueError("Frozen input drift: "+path)
def load_task(task_id):
    if task_id not in TASK_ORDER:raise ValueError("Only the frozen four pilot tasks are allowed")
    plan_path=OLD_RUN/"plan.json";plan=read_json(plan_path)
    if read_json(OLD_RUN/"plan.seal.json")["sha256"]!=sha256(plan_path):raise ValueError("Old plan seal mismatch")
    if plan["seed"]!=1 or plan["epochs"]!=50:raise ValueError("Unexpected frozen seed/schedule")
    job=next(j for j in plan["jobs"] if j["id"]==task_id+"_fold0")
    task=job["task"];cohort=job["cohort"];prep=Path(job["prepared"])
    prep_path=prep/"manifest.json";manifest=read_json(prep_path)
    splits=read_json(job["splits"]);validate_document(splits)
    if splits["prepared_manifest_sha256"]!=sha256(prep_path):raise ValueError("Old prepared/split mismatch")
    if splits["seed"]!=1 or splits["k_folds"]!=(5 if task=="contract" else 10):raise ValueError("Frozen split parameters differ")
    split=next(x for x in splits["folds"] if x["fold"]==0)
    config_path=OLD_RUN/"jobs"/job["id"]/"attempt_001/effective_config.json"
    oldconfig=read_json(config_path)
    if oldconfig["seed"]!=1 or oldconfig["patience"]!=7 or oldconfig["delta"]!=0.001 or oldconfig["schedule_epochs"]!=50:
        raise ValueError("Unexpected historical effective configuration")
    if oldconfig["prepared_manifest_sha256"]!=sha256(prep_path) or oldconfig["split_manifest_sha256"]!=sha256(job["splits"]):
        raise ValueError("Historical config input binding differs")
    config={k:copy.deepcopy(oldconfig[k]) for k in NUMERIC_KEYS}
    config.update(mode="full",maximum_training_epochs=50,environment=oldconfig["environment"])
    label_path=(prep/manifest["graph_labels"]["path"]).resolve()
    if sha256(label_path)!=manifest["graph_labels"]["sha256"]:raise ValueError("Label SHA mismatch")
    records=read_json(label_path);labels={x["contract_name"]:int(x["targets"]) for x in records}
    if len(labels)!=len(records) or any(y not in (0,1) for y in labels.values()):raise ValueError("Invalid labels")
    prov_path=ROOT/"scripts/DFG/experiments/audit/ddg_v11_correctness/D1_PROVENANCE.json"
    d1=read_json(prov_path)["graphs"][task_id];paths={"E2":Path(d1["path"])};hashes={"E2":d1["sha256"]}
    gmanifest_path=STAGE_F/"F3_attempt_002/GRAPH_MANIFEST.json"
    for record in read_json(gmanifest_path):
        if record["cohort"]==cohort and record["task"]==task:
            paths[record["variant"]]=Path(record["path"]);hashes[record["variant"]]=record["sha256"]
    if set(paths)!=set(VARIANTS):raise ValueError("Missing candidate variant")
    frozen_files={str(p):sha256(p) for p in (plan_path,OLD_RUN/"plan.seal.json",prep_path,Path(job["splits"]),config_path,label_path,prov_path,gmanifest_path)}
    for p,h in plan["frozen_files"].items():
        if p in frozen_files and frozen_files[p]!=h:raise ValueError("Frozen plan file mismatch: "+p)
    graphs={}
    for v in VARIANTS:
        if sha256(paths[v])!=hashes[v]:raise ValueError("Candidate graph SHA mismatch")
        frozen_files[str(paths[v])]=hashes[v];graphs[v]=read_graph(paths[v]);assert_disconnected_files(graphs[v])
    baseline=graphs["E2"];nodes=frozen(list(baseline.nodes(data=True)))
    population={d["source_file"] for _,d in baseline.nodes(data=True)}
    if sorted(population)!=splits["files"] or splits["file_labels"]!={f:labels[f] for f in sorted(population)}:raise ValueError("Population or label mismatch")
    if set(split["train_files"]) & set(split["val_files"]) or set(split["train_files"])|set(split["val_files"])!=population:
        raise ValueError("Supervision partition mismatch")
    for _,d in baseline.nodes(data=True):
        token=np.asarray(d["token"])
        if token.shape!=(512,) or token.dtype!=np.float32 or not np.isfinite(token).all():raise ValueError("Frozen tokenizer feature mismatch")
    invariants={}
    for v,g in graphs.items():
        if frozen(list(g.nodes(data=True)))!=nodes:raise ValueError("Variant node/label/feature/order mismatch")
        if v!="E2":invariants[v]=assert_preserved(baseline,g)
        counts=Counter(d["edge_type"] for _,_,d in g.edges(data=True))
        expected=(0,0,0) if v=="E2" else (EXPECTED[task_id][0],0,0) if v=="E3a" else EXPECTED[task_id]
        if tuple(counts[k] for k in RELATIONS)!=expected:raise ValueError("Candidate relation inventory differs")
    # Preserve the entire E3a multigraph when removing only E3b's order relations.
    clean=copy.deepcopy(graphs["E3b"])
    for s,t,k,d in list(clean.edges(keys=True,data=True)):
        if d["edge_type"] in RELATIONS[1:]:clean.remove_edge(s,t,k)
    if fingerprint(clean)!=fingerprint(graphs["E3a"]):raise ValueError("E3b does not preserve E3a")
    for source in manifest["sources"].values():frozen_files[source["path"]]=source["sha256"]
    for path,h in manifest["feature"]["asset_hashes"].items():frozen_files[path]=h
    check_hashes(frozen_files)
    info={"task_id":task_id,"task":task,"cohort":cohort,"fold":0,"config":config,
          "source_config":str(config_path),"source_config_sha256":sha256(config_path),
          "source_prepared_manifest":str(prep_path),"source_prepared_manifest_sha256":sha256(prep_path),
          "source_splits_path":job["splits"],"source_splits_sha256":sha256(job["splits"]),
          "split":split,"labels_path":str(label_path),"labels_sha256":sha256(label_path),
          "feature":manifest["feature"],"label_version":manifest["label_version"],"invariants":invariants,
          "graphs":{v:{"path":str(paths[v]),"sha256":hashes[v],"fingerprint":fingerprint(graphs[v]),"nodes":len(graphs[v]),
                       "edges":graphs[v].number_of_edges(),"node_attributes_sha256":digest(nodes),
                       "relation_counts":dict(Counter(d["edge_type"] for _,_,d in graphs[v].edges(data=True)))} for v in VARIANTS},
          "frozen_files":frozen_files}
    return info,graphs,labels
