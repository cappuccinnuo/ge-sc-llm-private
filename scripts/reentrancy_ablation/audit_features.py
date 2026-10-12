"""Check whether the all-node feature mismatch is serialization, not another LLM."""
import numpy as np
from common import *
from label_rules import canonical_code, align_graphs
from transformers import AutoTokenizer

def main():
    prepared=HERE/"artifacts/v1/prepared"
    a=read_graph(prepared/"A_author/contract.gpickle")
    d=read_graph(prepared/"D_local_features/contract.gpickle")
    local=read_graph(REPO/"scripts/labeling_v2/artifacts/labels_v1/source_range/contractlevel.gpickle")
    inverse={v:k for k,v in align_graphs(local,a).items()}
    tok=AutoTokenizer.from_pretrained("Salesforce/codet5p-770m",local_files_only=True,trust_remote_code=False)
    cache={}
    def encode(code):
        if code not in cache:
            ids=tok(code,add_special_tokens=True).input_ids
            out=np.full(512,tok.pad_token_id,dtype=np.float32)
            out[:min(len(ids),512)]=ids[:512];cache[code]=out
        return cache[code]
    raw_matches=0;decoded_matches=0;local_matches=0;failures=[]
    for n,attrs in a.nodes(data=True):
        raw_ok=np.array_equal(encode(attrs["code"]),attrs["token"])
        decoded_ok=np.array_equal(encode(canonical_code(attrs["code"])),d.nodes[n]["token"])
        raw_matches+=int(raw_ok);decoded_matches+=int(decoded_ok)
        local_matches+=int(np.array_equal(encode(local.nodes[inverse[n]]["code"]),d.nodes[n]["token"]))
        if not(raw_ok and decoded_ok):failures.append(n)
    report={"created_utc":utc(),"model":"Salesforce/codet5p-770m","tokenizer_class":type(tok).__name__,
            "nodes":len(a),"author_feature_matches_tokenizer_on_serialized_code":raw_matches,
            "local_feature_matches_tokenizer_on_actual_local_code":local_matches,
            "local_feature_matches_tokenizer_on_decoded_code":decoded_matches,"mismatch_nodes":failures,
            "note":"A reuses previous local tokenization of author graph strings including outer quotes/escaped newlines. D uses decoded source-code text. Neither vector set was supplied by the authors."}
    write_json(prepared.parent/"feature_text_audit.json",report);print(json.dumps(report))
if __name__=="__main__":main()
