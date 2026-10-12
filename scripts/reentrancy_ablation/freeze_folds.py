"""Freeze the actual historical AUTHOR HCG splits, by contract filename."""
from common import *

def freeze(task, expected_files, output):
    source = REPO / ("models/linelevel/author_hcg_line_v1" if task=="node" else
                     "models/contractlevel/author_hcg_contract_v1")
    paths = sorted(source.glob("*fold*/selection.json"),
                   key=lambda p: int(p.parent.name.split("fold")[-1]))
    expected_k = 10 if task=="node" else 5
    if len(paths)!=expected_k:
        raise ValueError("Missing original fold records")
    folds=[]; seen=Counter()
    for path in paths:
        record=read_json(path)
        train=sorted(record["train_files"]); val=sorted(record["val_files"])
        if len(set(train))!=len(train) or len(set(val))!=len(val):
            raise ValueError("Duplicate filenames in split")
        if set(train)&set(val) or set(train)|set(val)!=set(expected_files):
            raise ValueError("Fold population differs from reference")
        seen.update(val)
        folds.append({"fold":record["fold"], "train_files":train, "val_files":val,
                      "source_selection":str(path), "source_sha256":sha256(path)})
    if set(seen)!=set(expected_files) or any(n!=1 for n in seen.values()):
        raise ValueError("Each contract must be held out exactly once")
    result={"created_utc":utc(),"task":task,"k_folds":expected_k,"files":sorted(expected_files),
            "folds":folds,"split_hash":object_hash(folds),
            "note":"No repartitioning. These are author-HCG historical run splits, not author-paper original fold lists."}
    write_json(output,result)
    return result
