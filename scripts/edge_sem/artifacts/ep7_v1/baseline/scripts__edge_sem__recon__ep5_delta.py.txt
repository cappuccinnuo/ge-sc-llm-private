"""EP5 section 0: read-only archived EP4 verification and strict matrix delta."""
from collections import Counter
import numpy as np
from .common import ROOT, ref, read, checked, write
from .ep5_common import OUT, TASKS
from scripts.edge_sem.attr_batch import numeric_digest, load_attributes
from scripts.edge_sem.attrs import edge_rows
from scripts.edge_sem.build_f4 import load_edges
from scripts.node_sem.facts_io import load_context

OLD = ROOT/"scripts/edge_sem/artifacts/ep4_v1/attributes_attempt3"


def archived(task):
    """Verify archived source bytes, never relax the production loader."""
    before = read(OUT/"before.json")
    if not read(checked(before["historical_verification"]))["passed"]:
        raise ValueError("EP4 historical acceptance missing")
    history = {r["path"]:r for r in before["prior_artifacts"]}
    path = OLD/task/"manifest.json"
    checked(history[str(path)])
    seal = path.with_name("manifest.seal.json")
    checked(history[str(seal)])
    if read(seal)["manifest"] != ref(path):
        raise ValueError("EP4 seal differs")
    manifest = read(path)
    if manifest["task_id"] != task or manifest["version"] != "edgesem-attrs-v1":
        raise ValueError("EP4 identity differs")
    snapshots = {x["original"]["path"]:x for x in before["authorized_source_changes"]}
    for record in manifest["implementation"]:
        replacement = snapshots.get(record["path"], {}).get("snapshot", record)
        if record["sha256"] != replacement["sha256"]:
            raise ValueError("EP4 source snapshot differs")
        checked(replacement)
    for record in manifest["sources"].values(): checked(record)
    for record in manifest["input_provenance"]["graphs"].values(): checked(record)
    for name in ("plan","store","audit"): checked(manifest["input_provenance"][name])
    for name in ("attrs","diagnostics","facts","f4_manifest","layout","selection"):
        checked(manifest[name])
    for record in read(checked(manifest["selection"]))["per_task"].values(): checked(record)
    with np.load(checked(manifest["attrs"]),allow_pickle=False) as data:
        keys, values = data["edge_keys"].tolist(), data["attrs"].copy()
    if values.dtype != np.uint8 or values.shape != (manifest["rows"],74):
        raise ValueError("EP4 matrix metadata differs")
    if numeric_digest(keys,values) != manifest["numeric_digest"]:
        raise ValueError("EP4 numeric digest differs")
    return manifest,keys,values


def hard_delta(old_keys,old,new_keys,new):
    if old_keys != new_keys: raise ValueError("Edge key order differs")
    if old.shape != new.shape: raise ValueError("Matrix shape differs")
    other = [i for i in range(74) if i != 20]
    if not np.array_equal(old[:,other],new[:,other]):
        bad = np.argwhere(old[:,other] != new[:,other])
        raise ValueError("Unauthorized attribute differences: "+repr([(old_keys[r],other[c]) for r,c in bad[:30]]))
    if np.any(new[:,20] > old[:,20]):
        raise ValueError("New carried edges are not a subset")
    return dict(edge_keys_exact=True,other_73_columns_bitwise_exact=True,
                new_carried_subset=True,changed_bit20=int(np.sum(old[:,20]!=new[:,20])))


def main():
    summary = {}
    try:
        for task in TASKS:
            old_manifest,old_keys,old = archived(task)
            ctx = load_context(task);graph = ctx["graphs"]["F3"]
            path = OUT/"attributes"/task/"manifest.json";manifest = read(path)
            edges = load_edges(checked(manifest["f4_manifest"]))
            values = load_attributes(path,graph,edges)
            keys = list(values);new = np.stack(list(values.values()))
            delta = hard_delta(old_keys,old,keys,new)
            rows = edge_rows(graph,edges)
            counts = {}
            for relation in sorted({r["relation"] for r in rows}):
                indices = [i for i,r in enumerate(rows) if r["relation"] == relation]
                counts[relation] = dict(old=int(old[indices,20].sum()),new=int(new[indices,20].sum()))
            outliers = []
            bad = np.flatnonzero((new[:,20]==1)&(new[:,59]==0))
            if len(bad):
                from scripts.node_sem.facts import extract
                facts = extract(task,context=ctx)
                for i in bad:
                    row=rows[i];bound=facts[row["dst"]].get("loop",{}).get("bound","inapplicable")
                    outliers.append(dict(edge_key=row["key"],source=row["src"],target=row["dst"],
                                         file=row["file"],source_sha256=ctx["sources"][row["file"]]["sha256"],
                                         loop_bound=bound,documented_exception=bound=="unknown"))
            selection = read(checked(manifest["selection"]))
            previous = read(checked(old_manifest["selection"]))
            changes = {name:dict(added=sorted(set(selection[name])-set(previous[name])),
                                 removed=sorted(set(previous[name])-set(selection[name])))
                       for name in ("core_indices","context_indices")}
            summary[task] = dict(old_manifest=ref(OLD/task/"manifest.json"),manifest=ref(path),
                **delta,per_relation_bit20=counts,ctx_in_loop_zero=outliers,
                unexplained_ctx_in_loop_zero=sum(not x["documented_exception"] for x in outliers),
                endpoint_bit20=read(checked(selection["per_task"][task]))["20"],
                selection_changes=changes,source_view="original")
            print(task,counts["DATA_DEF_USE"],"delta verified",flush=True)
        write(OUT/"attribute_delta.json",dict(passed=True,tasks=summary,training_executed=False))
    except Exception as exc:
        write(OUT/"attribute_delta.failure.json",dict(passed=False,error=repr(exc),completed=summary))
        raise


if __name__=="__main__": main()
