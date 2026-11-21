from pathlib import Path
from collections import Counter, defaultdict
from dataclasses import asdict
import hashlib, json, os, subprocess, sys, time
B = Path(__file__).resolve().parent
ROOT = B.parents[2]
MOD = ROOT / 'compile_repair'
ART = B.parent
LOCAL = ROOT.parent / 'compile-repair-local' / B.name
sys.path.insert(0, str(ROOT))

def sha(data):
    return hashlib.sha256(data).hexdigest()

def save(name, data):
    with (B / name).open('x', encoding='utf8') as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
        fp.write('\n')

def saved(name):
    return json.loads((B / name).read_bytes())

def committed(path, commit='61c94e00'):
    expected = subprocess.check_output(['git', 'show', commit+':'+str(path.relative_to(ROOT))], cwd=str(ROOT))
    actual = path.read_bytes()
    assert actual == expected, path
    return actual

def members():
    inventory = ART/'cp3_continue_v1/unit_inventory.jsonl'
    provenance = ART/'cp3_paths_v1/result_provenance.json'
    units = [json.loads(line) for line in committed(inventory).splitlines()]
    refs = json.loads(committed(provenance))['rows']
    assert len(units) == 31307 and len(refs) == 31071
    return units, refs

def verified(path, digest):
    data = Path(path).read_bytes()
    if sha(data) != digest:
        raise ValueError('Hash mismatch: '+str(path))
    return data
