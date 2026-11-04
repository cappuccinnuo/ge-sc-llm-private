"""Diagnostic-only statistics and identity checks; no fitting or label-based graphs."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[4]
RUN = REPO / 'scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c'
PROTOCOL = 'frozen-checkpoint-ddg-diagnostics-v1'
SCORE_ROLE = 'exploratory_cv_validation_sensitivity'
# Declared before any model replay, never tuned to observed failures.
TOLERANCES = dict(archive_probability_atol=1e-6, archive_probability_rtol=1e-5,
                  archived_metric_atol=1e-10, native_wrapper='bitwise_equal',
                  restored_native='bitwise_equal', near_zero_denominator=1e-8)
PILOTS = [('reentrancy_author', 'contract', 0), ('access_control_author', 'contract', 0),
          ('reentrancy_author', 'node', 0), ('access_control_author', 'node', 0),
          ('reentrancy_author', 'node', 8), ('access_control_author', 'node', 7),
          ('access_control_author', 'node', 8)]
REWIRING_SEEDS = [101, 102, 103]

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf8'))

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf8') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=True, allow_nan=False)
        handle.write('\n')

def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('x', encoding='utf8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v,(dict,list,tuple)) else v
                             for k,v in row.items()})

def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for data in iter(lambda: handle.read(1024*1024), b''):
            digest.update(data)
    return digest.hexdigest()

def summary(values):
    a = np.asarray(values, dtype=np.float64).reshape(-1)
    if not np.isfinite(a).all():
        raise ValueError('Nonfinite diagnostic values')
    if not len(a):
        return dict(n=0,mean=None,median=None,p95=None,max=None,zero_fraction=None)
    return dict(n=int(len(a)),mean=float(a.mean()),median=float(np.median(a)),
                p95=float(np.percentile(a,95)),max=float(a.max()),
                zero_fraction=float(np.mean(a==0)))

def identity(row, task):
    if task == 'node':
        value = row['original_graph_node_id']
        return (row['file'], type(value).__name__, value)
    return (row['file'],)

def align_records(records, expected, task):
    lookup = {}
    for row in records:
        key = identity(row, task)
        if key in lookup:
            raise ValueError('Duplicate prediction identity')
        lookup[key] = row
    keys = [identity(row,task) for row in expected]
    if len(keys)!=len(set(keys)) or set(keys)!=set(lookup):
        raise ValueError('Prediction population/identity mismatch')
    aligned = [lookup[key] for key in keys]
    if [r['target'] for r in aligned] != [r['target'] for r in expected]:
        raise ValueError('Prediction target mismatch')
    return aligned

def compare_outputs(y, reference_logits, logits, files):
    from scripts.DFG.experiments.common import metrics
    import torch
    reference_logits = np.asarray(reference_logits)
    logits = np.asarray(logits)
    if logits.shape != reference_logits.shape or logits.shape != (len(y),2):
        raise ValueError('Misaligned diagnostic outputs')
    if not np.isfinite(logits).all() or not np.isfinite(reference_logits).all():
        raise ValueError('Nonfinite diagnostic logits')
    probability = torch.from_numpy(logits).softmax(1)[:,1].numpy()
    reference_probability = torch.from_numpy(reference_logits).softmax(1)[:,1].numpy()
    pred = logits.argmax(1); ref = reference_logits.argmax(1); truth=np.asarray(y)
    changed = pred != ref
    corrected = (ref != truth) & (pred == truth)
    introduced = (ref == truth) & (pred != truth)
    row = dict(metrics(list(y),pred.tolist()), prediction_flips=int(changed.sum()),
               prediction_flip_fraction=float(changed.mean()), corrected=int(corrected.sum()),
               introduced=int(introduced.sum()),
               logits_exact=bool(np.array_equal(logits,reference_logits)),
               probabilities_exact=bool(np.array_equal(probability,reference_probability)),
               predictions_exact=bool(np.array_equal(pred,ref)))
    for prefix, values in [('logit_abs',np.abs(logits-reference_logits)),
                           ('probability_abs',np.abs(probability-reference_probability))]:
        row.update({prefix+'_'+k:v for k,v in summary(values).items()})
    by_file=[]
    for file in sorted(set(files)):
        mask=np.asarray([f==file for f in files])
        by_file.append(dict(file=file,n=int(mask.sum()),flips=int(changed[mask].sum()),
                            corrected=int(corrected[mask].sum()),introduced=int(introduced[mask].sum()),
                            probability_abs_mean=float(np.abs(probability-reference_probability)[mask].mean())))
    return row, by_file, probability.tolist()
