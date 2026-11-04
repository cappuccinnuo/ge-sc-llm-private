"""Prompt 0 original scalar baseline rerun; no analyzer modifications."""
import argparse
from collections import Counter
from pathlib import Path
import time
from scripts.DFG.frontend import parse, walk, FUNCTION_TYPES
from scripts.DFG.integration.io import read_json, checked, read_sources, write_json, write_bundle, sha256
from scripts.DFG.integration.pipeline import build_graph
from scripts.DFG.integration.rebuild import DEFAULT_MANIFEST
from scripts.labeling_v2.safe_graph import read_graph


def run(output):
    output=Path(output).resolve()
    if output.exists():raise FileExistsError(str(output))
    checked(DEFAULT_MANIFEST,read_json(DEFAULT_MANIFEST.with_name('manifest.seal.json'))['sha256'])
    manifest=read_json(DEFAULT_MANIFEST);output.mkdir(parents=True);records=[]
    for ref in manifest['tasks']:
        start=time.monotonic();tid=ref['task_id'];print(tid,flush=True)
        task=read_json(checked(ref['source_task_manifest'],ref['source_task_sha256']))
        rec=task['graphs']['HCG'];p=checked(rec['path'],rec['sha256']);graph=read_graph(p)
        sp=checked(ref['source_metadata_manifest'],ref['source_metadata_sha256'])
        sources,metadata,used,missing=read_sources(sp,graph)
        # The P0 comparator must stay the old scalar. SupportedSourceView approval
        # concerns v2's future frontend, not rewriting the baseline under test.
        enhanced,audit=build_graph(graph,sources,profile='scalar',metadata=metadata)
        scalar=audit['stages']['scalar'];totals=Counter();reasons=Counter();file_reasons=Counter()
        for record in scalar['files'].values():
            totals.update(record.get('analysis',{}))
            for d in record.get('diagnostics',[]):
                if d.get('kind')=='function_fallback':reasons[d.get('reason','unknown')]+=1
                if d.get('kind') in ('file_fallback','projection_fallback'):file_reasons[d.get('reason','unknown')]+=1
        raw_total=sum(sum(n.type in FUNCTION_TYPES and n.child_by_field_name('body') is not None
                          for n in walk(parse(code).root_node)) for code in sources.values())
        inputs={'original_graph':rec,'source_manifest':str(sp),'source_manifest_sha256':sha256(sp),'sources':used,'missing_sources':missing}
        bundle=write_bundle(output/tid,enhanced,audit,inputs)
        checked(p,rec['sha256'])
        for source in used.values():checked(source['path'],source['sha256'])
        entry={'task_id':tid,'raw_functions_with_body':raw_total,'functions_in_analyzable_files':totals['functions_total'],'functions_supported':totals['functions_supported'],'functions_excluded_by_file_gate':raw_total-totals['functions_total'],'DATA_DEF_USE':audit['invariants']['added_by_relation'].get('DATA_DEF_USE',0),'function_fallback_top10':reasons.most_common(10),'all_function_fallback_reasons':dict(reasons),'file_fallback_reasons':dict(file_reasons),'bundle':bundle,'seconds':time.monotonic()-start}
        records.append(entry);print(tid,entry['functions_supported'],raw_total,entry['DATA_DEF_USE'],flush=True)
    result={'profile':'scalar','old_analyzer_unchanged':True,'new_training':False,'tasks':records}
    write_json(output/'summary.json',result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(p.parse_args().output)
