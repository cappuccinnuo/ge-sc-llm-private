"""Read-only reproduction of archived DOT failures using the exact frozen sources."""
import ast
import hashlib
import importlib.util
import json
import os
import pickle
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[6]
ARCHIVE=Path('/home/zhao/SmartContract/ge-sc-llm')
sys.path.insert(0,str(ROOT))
os.environ.setdefault('TREE_SITTER_LIB_DIR',str(ARCHIVE/'build/linux-x86_64'))
from scripts.DFG.frontend import SourceView
from scripts.DFG.projection import Projector,code_equal
from scripts.DFG.models import Unsupported


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out=Path(__file__).parent/'author_projection_before_after.json'
    if out.exists():raise RuntimeError('Refuse to overwrite prior evidence')
    old_path=ARCHIVE/'scripts/DFG/projection.py'
    spec=importlib.util.spec_from_file_location('scripts.DFG._projection_archive',str(old_path))
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    evidence_path=ARCHIVE/'scripts/DFG/experiments/audit/ddg_diagnostics_v1/case_evidence.json'
    evidence=json.loads(evidence_path.read_text())['dot_projection_probe']
    rows=[];loaded={}
    for case in evidence:
        cohort=case['cohort'];file=case['file']
        if cohort not in loaded:
            prepared=ARCHIVE/'scripts/DFG/experiments/artifacts/20261012_v1'/cohort/'prepared'
            source_manifest=json.loads((prepared/'source_manifest.json').read_text())
            gp=prepared/'E0/contract.gpickle'
            with gp.open('rb') as f:graph=pickle.load(f)
            loaded[cohort]=(source_manifest,graph,gp,sha(gp))
        manifest,graph,gp,graphsha=loaded[cohort]
        source=Path(manifest[file]['path'])
        assert sha(source)==manifest[file]['sha256']
        view=SourceView(source.read_text(),file)
        node=case['node_id'];stored=graph.nodes[node]['code']
        assert stored==ast.literal_eval(case['stored_code_repr'])
        expected=ast.literal_eval(case['expected_code_repr'])
        row={'cohort':cohort,'file':file,'first_failed_node':node,
             'source_path':str(source),'source_sha256':sha(source),
             'graph_path':str(gp),'graph_sha256':graphsha,
             'old_code_equal':old.code_equal(stored,expected),
             'new_code_equal':code_equal(stored,expected)}
        try:old.Projector(graph,view)
        except Unsupported as exc:row['old_projection_error']=str(exc)
        else:raise AssertionError('Baseline failure no longer reproduced')
        fixed=Projector(graph,view)
        row['new_projection_stats']=fixed.stats
        assert not row['old_code_equal'] and row['new_code_equal']
        rows.append(row)
    result={'status':'passed','count':len(rows),'cases':rows,
            'baseline_projection_sha256':sha(old_path),
            'fixed_projection_sha256':sha(ROOT/'scripts/DFG/projection.py'),
            'archived_evidence_sha256':sha(evidence_path),
            'compilation_validation':'Not executed: parser/source projection only; no solc download or execution',
            'identity_limit':'Exact canonical DOT serialization plus AST anchors does not prove historical author source bytes; known multiline literal collisions are conservatively rejected.'}
    with out.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({'status':result['status'],'recovered_files':len(rows),
       'verified_existing_nodes':sum(r['new_projection_stats']['ordinary_nodes_checked'] for r in rows)}))

if __name__=='__main__':main()
