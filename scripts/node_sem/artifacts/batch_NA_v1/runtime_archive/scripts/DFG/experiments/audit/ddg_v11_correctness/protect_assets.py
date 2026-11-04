"""Protect the original archive; new worktree is the only development location."""
import argparse, hashlib, json, subprocess, time
from pathlib import Path
ORIGINAL=Path('/home/zhao/SmartContract/ge-sc-llm')
OUT=Path(__file__).resolve().parent
DOCS=['HANDOVER.md','docs/training_changes_2026-10-07.md']
TREES=['scripts/DFG/experiments/audit/ddg_diagnostics_v1',
       'scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c',
       'scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1',
       'scripts/DFG/tests','tests']
def unexpected_files(known, candidates):
    return sorted(str(f) for f in candidates if str(f) not in known)
def protected_candidates():
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=str(ORIGINAL)).decode().split('\0')
    paths={ORIGINAL/s for s in tracked if s}
    paths.update((ORIGINAL/'scripts/DFG').glob('*.py'))
    for rel in TREES:
        paths.update(f for f in (ORIGINAL/rel).rglob('*') if f.is_file() and '__pycache__' not in f.parts)
    return paths
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def dump(path,data):
    with Path(path).open('x',encoding='utf8') as f:json.dump(data,f,indent=2,sort_keys=True)
def head():
    return subprocess.check_output(['git','rev-parse','HEAD'],cwd=str(ORIGINAL)).decode().strip()
def main():
    p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');a=p.parse_args()
    if not a.final:
        old=json.loads((ORIGINAL/'scripts/DFG/experiments/audit/ddg_diagnostics_v1/archive/before.json').read_text())
        paths={Path(s) for s in old['snapshot']}
        tracked=subprocess.check_output(['git','ls-files','-z'],cwd=str(ORIGINAL)).decode().split('\0')
        paths.update(ORIGINAL/s for s in tracked if s)
        diag=ORIGINAL/'scripts/DFG/experiments/audit/ddg_diagnostics_v1'
        paths.update(f for f in diag.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
        for n in DOCS:
            dst=OUT/(Path(n).name+'.before')
            with dst.open('xb') as f:f.write((ORIGINAL/n).read_bytes())
        records={str(f):{'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(paths)}
        dump(OUT/'protected_before.json',{'head':head(),'files':records,'append_only_documents':DOCS})
        print(json.dumps({'protected':len(records),'head':head()}),flush=True)
    else:
        before=json.loads((OUT/'protected_before.json').read_text())
        changes=[];docs=[]
        for s,r in before['files'].items():
            f=Path(s)
            if not f.is_file():changes.append({'path':s,'reason':'missing'});continue
            digest=sha(f)
            if digest!=r['sha256']:
                rel=str(f.relative_to(ORIGINAL)) if ORIGINAL in f.parents else None
                if rel in DOCS:
                    prefix=(OUT/(f.name+'.before')).read_bytes()
                    assert f.read_bytes().startswith(prefix),'Historical doc bytes altered'
                    docs.append({'path':s,'before':r['sha256'],'after':digest,'prefix_preserved':True})
                else:changes.append({'path':s,'before':r['sha256'],'after':digest})
        new_files=unexpected_files(before['files'],protected_candidates())
        result={'unexpected_new_files':new_files,'checked':len(before['files']),'head_unchanged':head()==before['head'],
                'unexpected_changes':changes,'authorized_document_appends':docs}
        result['passed']=not changes and not new_files and result['head_unchanged']
        dump(OUT/'protected_after.json',result);print(json.dumps(result),flush=True)
        assert result['passed']
if __name__=='__main__':main()
