"""Explain loop-context discrepancies using exact AST identity, without edits."""
from collections import Counter
from .common import read,write
from .ep5_common import OUT
from scripts.node_sem.facts_io import load_context
from scripts.edge_sem.attr_sources import AttributeSource

def main():
    records={}
    delta=read(OUT/"attribute_delta.json")
    for task,result in delta["tasks"].items():
        ctx=load_context(task);cache={};rows=[]
        for row in result["ctx_in_loop_zero"]:
            file=row["file"]
            if file not in cache:cache[file]=AttributeSource(ctx["source_text"][file],file,ctx["graphs"]["F3"],ctx["sources"][file].get("metadata"))
            source=cache[file];ast=source.raw[row["target"]]
            parents=[];cursor=ast.parent
            while cursor is not None:
                parents.append(cursor.type);cursor=cursor.parent
            rows.append(dict(row,target_ast_type=ast.type,ancestors=parents,
                target_code=source.sem.text(ast)[:180],
                target_is_loop_header=ast.type in ("for_statement","while_statement","do_while_statement")))
        records[task]=dict(count=len(rows),target_types=dict(Counter(r["target_ast_type"] for r in rows)),rows=rows,
                           all_loop_headers=all(r["target_is_loop_header"] for r in rows))
        print(task,records[task]["count"],records[task]["target_types"],flush=True)
    write(OUT/"loop_context_audit.json",records)

if __name__=="__main__":main()
