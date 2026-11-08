# Copied from offline/llm_profile.py; SHA256 c7fea91186a5f3a93a2873039c158e791054a260c648d265f54093e32a838085.
# NS-P7b versioned adapter; the original remains immutable.
"""Token-only NS-P7 context audit. No generated responses or sampling changes."""
import argparse
import json
from pathlib import Path
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from llm_protocol_v2 import messages
from llm_assets import load
from asset_registry import read, checked, reference, write
from encode import gpu_lock, GPU_LOCK


def profile(inputs_path, assets_path, selected_path, out):
    asset=load(assets_path)
    inputs=read(inputs_path)
    selected=read(selected_path)["selected"]
    units=[json.loads(s) for s in checked(inputs["units"]).read_text(encoding="utf8").splitlines()]
    with gpu_lock(GPU_LOCK,"cuda"):
        from llama_cpp import Llama, llama_chat_format as cf
        model=Llama(model_path=str(checked(asset["model"])),n_ctx=4096,n_gpu_layers=0,vocab_only=True,verbose=False)
        if model.chat_format=="chatml":
            formatter=cf.format_chatml
        elif model.chat_format=="chat_template.default":
            formatter=cf.Jinja2ChatFormatter(model.metadata["tokenizer.chat_template"],
                model.detokenize([model.token_eos()],special=True).decode(),
                model.detokenize([model.token_bos()],special=True).decode())
        else:
            raise ValueError("Unsupported audited chat formatter: "+str(model.chat_format))
        rows=[]
        for unit in units:
            formatted=formatter(messages=messages(unit))
            count=len(model.tokenize(formatted.prompt.encode("utf8"),add_bos=not formatted.added_special,special=True))
            rows.append(dict(cache_key=unit["cache_key"],prompt_tokens=count,
                target_lines=len(unit["target_lines"]),within_context=count<4096,
                maximum_completion_tokens=min(2048,max(0,4096-count))))
        chat_format=model.chat_format
        del model
    table={r["cache_key"]:r for r in rows}
    subset=[table[s["cache_key"]] for s in selected]
    lengths=[r["prompt_tokens"] for r in rows]
    result=dict(inputs=reference(inputs_path),assets=reference(assets_path),selection=reference(selected_path),
        chat_format=chat_format,unique_prompts=len(rows),prompt_tokens_min=min(lengths),
        prompt_tokens_median=statistics.median(lengths),prompt_tokens_max=max(lengths),
        overflow_all=sum(not r["within_context"] for r in rows),
        pilot_overflow=sum(not r["within_context"] for r in subset),
        pilot_rows=subset,rows=rows,implementation=reference(__file__),generated_tokens=0)
    write(out,result)
    return {k:v for k,v in result.items() if k not in ("rows","pilot_rows")}


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    for key in ("inputs","assets","selection","out"):ap.add_argument("--"+key,required=True)
    a=ap.parse_args()
    print(json.dumps(profile(a.inputs,a.assets,a.selection,a.out),indent=2))
