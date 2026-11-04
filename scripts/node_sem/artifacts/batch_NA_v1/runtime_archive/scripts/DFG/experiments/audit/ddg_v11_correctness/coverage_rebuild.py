"""Rebuild only scalar DDG in a new directory; compare against accepted E1."""
import argparse,csv,json,sys,hashlib,subprocess
from pathlib import Path
from collections import Counter
OUT=Path(__file__).resolve().parent
ORIGINAL=Path('/home/zhao/SmartContract/ge-sc-llm')
def read(p):return json.loads(Path(p).read_text())
def dump(p,d):
    with Path(p).open('x',encoding='utf8') as f:json.dump(d,f,ensure_ascii=True,indent=2)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def csvout(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with Path(p).open('x',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def semantic_edges(g,audit):
    out=[]
    for s,t,k,d in g.edges(keys=True,data=True):
        if d['edge_type']!='DATA_DEF_USE':continue
        facts=[audit['evidence'][i] for i in d['ddg_fact_indices']]
        assert facts and all(f['source']==s and f['target']==t for f in facts)
        assert all(f['function'].startswith(g.nodes[s]['source_file']+':') for f in facts)
        out.append({'file':g.nodes[s]['source_file'],'source':s,'target':t,
           'canonical':[g.nodes[s]['node_type'],'DATA_DEF_USE',g.nodes[t]['node_type']],
           'facts':sorted(facts,key=lambda f:(f['symbol'],f['definition'],f['use']))})
    return sorted(out,key=lambda r:(r['file'],r['source'],r['target']))
def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--stage',choices=['before','after'],required=True);args=p.parse_args()
    sys.path.insert(0,str(args.repo))
    from scripts.DFG import __version__
    from scripts.DFG.pipeline import augment
    from scripts.DFG.graph_audit import fingerprint,assert_augmented
    from scripts.DFG.experiments.audit.ddg_diagnostics_v1.static_analysis import (
      resolved_tasks,load_pair,checked,replay_coverage,coverage_summary)
    from scripts.labeling_v2.safe_graph import write_graph,read_graph
    import scripts.DFG.projection as projection
    assert str(Path(projection.__file__).resolve()).startswith(str(args.repo.resolve())+'/')
    folder=OUT/args.stage;folder.mkdir(exist_ok=False)
    inputs={};groups=resolved_tasks(ORIGINAL/'scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c',inputs)
    allfiles=[];allfns=[];allfacts=[];summaries={};alladded=[]
    for cohort in ['reentrancy_author','access_control_author']:
        ck=cohort+'_contract';group=groups[ck]
        manifest,old_audit,base,archived=load_pair(group,inputs)
        mpath=group['prepared']/'manifest.json'
        old_graph_sha=fingerprint(archived);base_sha=fingerprint(base)
        sources={f:checked(info['path'],info['sha256'],inputs).read_text(encoding='utf8')
                 for f,info in manifest['sources'].items()}
        modes={f:r.get('scope_mode') for f,r in old_audit['files'].items()}
        print(args.stage+' rebuilding '+cohort,flush=True)
        enhanced,audit=augment(base,sources,scope_modes=modes)
        assert_augmented(base,enhanced)
        assert fingerprint(base)==base_sha and fingerprint(archived)==old_graph_sha
        oldedges=semantic_edges(archived,old_audit);newedges=semantic_edges(enhanced,audit)
        oldby={(r['source'],r['target']):r for r in oldedges}
        newby={(r['source'],r['target']):r for r in newedges}
        if args.stage=='before':
            assert oldedges==newedges,'Old source replay differs from frozen semantic edges/facts'
        else:
            assert set(oldby)<=set(newby),'Fix removed old DDG endpoints'
            for key,r in oldby.items():
                assert r==newby[key], 'Existing edge provenance changed unexpectedly'
        fs,fns,facts,nodefns=replay_coverage(base,manifest,audit,inputs)
        # This independently reproduces all facts from the exact semantic CFG/RD.
        for task in ['contract','node']:
            key=cohort+'_'+task
            _,_,taskbase,taskold=load_pair(groups[key],inputs)
            pop={d['source_file'] for _,d in taskbase.nodes(data=True)}
            current=enhanced if task=='contract' else enhanced.subgraph(list(taskbase)).copy()
            assert_augmented(taskbase,current)
            sf=[dict(r,task_key=key) for r in fs if r['file'] in pop]
            sn=[dict(r,task_key=key) for r in fns if r['file'] in pop]
            st=[dict(r,task_key=key) for r in facts if r['file'] in pop]
            olde=semantic_edges(taskold,old_audit);newe=semantic_edges(current,audit)
            oldpairs={(r['source'],r['target']) for r in olde}
            added=[dict(r,task_key=key) for r in newe if (r['source'],r['target']) not in oldpairs]
            oldcanonical={tuple(r['canonical']) for r in olde}
            newcanonical={tuple(r['canonical']) for r in newe}
            byfile_old={f:[r for r in olde if r['file']==f] for f in pop}
            byfile_new={f:[r for r in newe if r['file']==f] for f in pop}
            changed=[f for f in sorted(pop) if byfile_old[f]!=byfile_new[f]]
            causes={}
            for f in changed:
                prior=old_audit['files'][f]
                reasons=[d.get('reason','') for d in prior.get('diagnostics',[])]
                tags=[]
                if any(d['kind']=='projection_fallback' for d in prior.get('diagnostics',[])):
                    tags.append('exact_dot_projection_recovered')
                if any('comment' in r for r in reasons):
                    tags.append('if_comment_branch_recovered')
                assert tags, 'Changed file not explained by either fix: '+f
                causes[f]={'fixes':tags,'previous_reasons':reasons,
                           'old_edges':len(byfile_old[f]),'new_edges':len(byfile_new[f])}
            for r in added:
                r['cause']=causes[r['file']]
                # Every emitted edge is traced to exact raw-span fact rows.
                supporting=[]
                for ev in r['facts']:
                    matches=[f for f in st if f['definition']==ev['definition'] and f['use']==ev['use'] and f['symbol']==ev['symbol']]
                    assert len(matches)==1
                    assert matches[0]['source']==r['source'] and matches[0]['target']==r['target']
                    supporting.append(matches[0])
                r['raw_fact_details']=supporting
            summary=coverage_summary(sf,sn,st)
            summary.update(task_key=key,original_base_sha256=fingerprint(taskbase),
               original_E1_sha256=fingerprint(taskold),new_graph_sha256=fingerprint(current),
               ddg_edges_before=len(olde),ddg_edges_after=len(newe),
               added_edges=len(added),removed_edges=0,changed_files=changed,change_causes=causes,
               unchanged_files=len(pop)-len(changed),all_previous_semantic_edges_and_evidence_unchanged=True,
               canonical_before=[list(x) for x in sorted(oldcanonical)],
               canonical_after=[list(x) for x in sorted(newcanonical)],
               new_canonical=[list(x) for x in sorted(newcanonical-oldcanonical)])
            if args.stage=='after':
                destination=folder/cohort;destination.mkdir(exist_ok=True)
                path=destination/('E2_'+task+'.gpickle')
                write_graph(current,path)
                assert fingerprint(read_graph(path))==fingerprint(current)
                summary['graph_file']={'path':str(path),'sha256':sha(path)}
            dump(folder/(key+'_semantic_edges.json'),newe)
            allfiles.extend(sf);allfns.extend(sn);allfacts.extend(st);alladded.extend(added)
            summaries[key]=summary
            print(json.dumps({'task':key,'counts':summary['counts'],
                 'added_edges':len(added),'changed_files':changed,'new_canonical':summary['new_canonical']}),flush=True)
        dump(folder/(cohort+'_audit.json'),audit)
        dump(folder/(cohort+'_input_manifest.json'),manifest)
    csvout(folder/'coverage.csv',allfiles);csvout(folder/'function_coverage.csv',allfns)
    csvout(folder/'facts.csv',allfacts);dump(folder/'added_edges_with_evidence.json',alladded)
    runtime={str(f.relative_to(args.repo)):sha(f) for f in (args.repo/'scripts/DFG').glob('*.py')}
    assert all(sha(p)==digest for p,digest in inputs.items()),'Frozen input drift'
    result={'status':'passed','stage':args.stage,'version':__version__,
            'experiment_version':'ddg-v1.1-correctness-fix' if args.stage=='after' else 'sealed-v1-replay',
            'imported_repo':str(args.repo),'runtime_code_sha256':runtime,'tasks':summaries,
            'input_hashes':inputs,'new_training_performed':False,
            'original_nodes_features_labels_spans_base_edges_preserved':True,
            'old_ddg_version_and_evidence_indices':'Version and global side-table indices may change; semantic evidence compared exactly',
            'node_population':'Exact existing task node IDs; induced from new full contract graph',
            'label_version':'released_author_node_labels'}
    dump(folder/'summary.json',result)
    print('Complete '+args.stage,flush=True)
if __name__=='__main__':main()
