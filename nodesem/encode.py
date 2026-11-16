"""Text encoders: CodeT5+ (CODE, CTX) and BGE (teacher), at pinned Hugging Face revisions.

* CODE: ``Salesforce/codet5p-110m-embedding``, the model's own normalized 256-d
  output, at most 128 tokens per node text.
* CTX: the same model over the rendered CTX fields, trimmed field by field to a
  256-token budget (``truncate``), never cut by the tokenizer.
* TEACHER: ``BAAI/bge-small-en-v1.5`` through sentence-transformers (CLS pooling,
  normalized, 384-d), fp32.

Identical texts are encoded once, in a deterministic length-then-SHA order. On a GPU
CODE/CTX run in fp16 (as in the original runs), so vectors match to fp16 precision,
not bit for bit, across devices.
"""
import hashlib
import json
from collections import OrderedDict

import numpy as np

MODELS = {
    "codet5p-110m-embedding": dict(repo_id="Salesforce/codet5p-110m-embedding",
                                   revision="d9f3a534af4252f04b10cd9f78e05037542d10f6",
                                   dimension=256, pooling="model_default"),
    "bge-small-en-v1.5": dict(repo_id="BAAI/bge-small-en-v1.5",
                              revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a", dimension=384, pooling="cls"),
}
CODE_MAX_LENGTH = 128
CTX_LIMIT = 256


BUDGET_VERSION = "nodesem-ctx-budget-v1"


FALLBACK_ORDER=("TO","FROM","FN_SUMMARY","CONTRACT","STATE_DECL","GUARD","COND",
                "PRE_EXT_CALL","CALL","LOOP","ENV","STATE_R","STATE_W","FUNC","USE","DEF","STMT")


def render(fields):
    return "\n".join("["+key+"] "+" | ".join(value) for key,value in fields.items())


def truncate(fields,tokenizer,limit=256):
    fields=OrderedDict((k,list(v)) for k,v in fields.items())
    if any(not v or not all(isinstance(x,str) for x in v) for v in fields.values()):
        raise ValueError("CTX fields must contain nonempty lists of strings")
    def length():return len(tokenizer.encode(render(fields),add_special_tokens=True))
    original=length()
    stage=0
    history=[dict(stage=0,tokens=original)]
    for level in range(1,8):
        if length()<=limit:break
        stage=level
        if level==1:
            for k in ("TO","FROM"):
                if k in fields:fields[k]=fields[k][:1]
        elif level==2:
            for k in ("FN_SUMMARY","CONTRACT","STATE_DECL"):
                if k in fields:fields[k]=fields[k][:4]
        elif level==3:
            for k,prefixes in (("GUARD",("kind:","eq:")),("COND",("eq:",))):
                if k in fields and fields[k] not in (["-"],["unknown"]):
                    fields[k]=[v for v in fields[k] if v.startswith(prefixes)] or ["-"]
        elif level==4:
            if "PRE_EXT_CALL" in fields:
                fields["PRE_EXT_CALL"]=[v.split(": ",1)[0] for v in fields["PRE_EXT_CALL"]]
            if "CALL" in fields and fields["CALL"] not in (["-"],["unknown"],["uninvoked_call_value"]):
                fields["CALL"]=[v for v in fields["CALL"] if v.startswith(("kinds:","target:"))]
        elif level==5:
            for k in ("DEF","USE"):
                if k in fields:
                    counts={};kept=[]
                    for value in fields[k]:
                        role=value.split(":")[1] if ":" in value else "none"
                        counts[role]=counts.get(role,0)+1
                        if counts[role]<=3:kept.append(value)
                    fields[k]=kept or ["-"]
            for k in ("STATE_R","STATE_W","ENV"):
                if k in fields:fields[k]=fields[k][:3]
        elif level==6:
            if "FUNC" in fields:
                fields["FUNC"]=[v for v in fields["FUNC"] if v.startswith(("visibility:","guards:"))] or ["-"]
        else:
            _trim_field(fields,"STMT",tokenizer,limit)
        history.append(dict(stage=level,tokens=length()))
    fallback=[]
    if length()>limit:
        stage=8
        for key in FALLBACK_ORDER:
            if length()<=limit:break
            if key in fields:
                before=list(fields[key])
                _trim_field(fields,key,tokenizer,limit)
                if fields[key]!=before:fallback.append(key)
        history.append(dict(stage=8,tokens=length()))
    if length()>limit:raise ValueError("CTX field labels alone exceed token budget")
    return render(fields),dict(stage=stage,original_tokens=original,final_tokens=length(),
        history=history,fallback_fields=fallback,retained_fields=list(fields))


def _trim_field(fields,key,tokenizer,limit):
    if key not in fields:return
    text=" | ".join(fields[key])
    # Prefix truncation is measured by the actual tokenizer after every update.
    # Never decode a truncated BPE sequence into invalid Unicode.
    while len(tokenizer.encode(render(fields),add_special_tokens=True))>limit and text:
        current=len(tokenizer.encode(render(fields),add_special_tokens=True))
        remove=max(1,min(len(text), (current-limit)*2))
        text=text[:-remove]
        fields[key]=[text if text else "-"]
    if not text:fields[key]=["-"]


def cache_key(text, asset_digest, max_length, pooling):
    raw = json.dumps([asset_digest, max_length, pooling, text],
                     ensure_ascii=False, separators=(",", ":")).encode("utf8")
    return hashlib.sha256(raw).hexdigest()


def schedule(texts, lengths):
    return sorted(range(len(texts)), key=lambda i: (
        lengths[i], hashlib.sha256(texts[i].encode()).hexdigest()))


def mean_pool(hidden, mask):
    weights = mask.unsqueeze(-1).to(hidden.dtype)
    return (hidden * weights).sum(1) / weights.sum(1).clamp(min=1)


def encode_unique(texts, tokenizer, model, device, max_length, pooling, batch_size, dim):
    import numpy as np
    import torch
    # Lengths are diagnostic and batching metadata, never a model input channel.
    lengths = [len(ids) for ids in tokenizer(texts, truncation=False,
               add_special_tokens=True)["input_ids"]] if texts else []
    order = schedule(texts, lengths)
    result = np.empty((len(texts), dim), dtype=np.float32)
    batches = []
    with torch.inference_mode():
        for start in range(0, len(order), batch_size):
            indices = order[start:start + batch_size]
            batch = tokenizer([texts[i] for i in indices], padding=True, truncation=True,
                              max_length=max_length, return_tensors="pt")
            batch = {key: value.to(device) for key, value in batch.items()}
            output = model(**batch)
            vector = output if pooling == "model_default" else mean_pool(
                output.last_hidden_state, batch["attention_mask"])
            if vector.shape != (len(indices), dim) or not torch.isfinite(vector).all():
                raise ValueError("Non-finite or incorrectly shaped encoder output")
            result[indices] = vector.float().cpu().numpy()
            batches.append(len(indices))
    return result, dict(unique_token_lengths=lengths,
                        truncated_unique=sum(n > max_length for n in lengths),
                        batch_count=len(batches), batch_sizes=batches)


def _deterministic_torch(device):
    import torch
    torch.manual_seed(1)
    torch.use_deterministic_algorithms(True, warn_only=device != "cpu")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    return torch


def load_codet5(device="cuda", cache_dir=None):
    torch = _deterministic_torch(device)
    import transformers
    spec = MODELS["codet5p-110m-embedding"]
    dtype = torch.float16 if device != "cpu" else torch.float32
    tokenizer = transformers.AutoTokenizer.from_pretrained(
        spec["repo_id"], revision=spec["revision"], trust_remote_code=True, cache_dir=cache_dir, use_fast=True)
    model = transformers.AutoModel.from_pretrained(
        spec["repo_id"], revision=spec["revision"], trust_remote_code=True, cache_dir=cache_dir,
        torch_dtype=dtype, attn_implementation="eager").to(device)
    model.eval()
    model.requires_grad_(False)
    return tokenizer, model


def encode_texts(texts, tokenizer, model, device, max_length, batch_size=32):
    """Encode row texts; identical texts share one forward. Returns float32 (n, 256)."""
    unique, index = [], {}
    for text in texts:
        if text not in index:
            index[text] = len(unique)
            unique.append(text)
    values, diagnostics = encode_unique(unique, tokenizer, model, device, max_length, "model_default",
                                        batch_size, MODELS["codet5p-110m-embedding"]["dimension"])
    return values[[index[t] for t in texts]], diagnostics


def ctx_texts(rows, tokenizer):
    """Budgeted CTX text per row (cached by the fields digest)."""
    cache, out = {}, []
    for row in rows:
        key = row["fields_sha256"]
        if key not in cache:
            fields = OrderedDict((k, row["fields"][k]) for k in row["field_order"])
            cache[key] = truncate(fields, tokenizer, CTX_LIMIT)
        out.append(cache[key])
    return out


def encode_code(text_rows, device="cuda", batch_size=32, cache_dir=None):
    tokenizer, model = load_codet5(device, cache_dir)
    return encode_texts([r["text"] for r in text_rows], tokenizer, model, device, CODE_MAX_LENGTH, batch_size)[0]


def encode_ctx(ctx_rows, device="cuda", batch_size=32, cache_dir=None):
    tokenizer, model = load_codet5(device, cache_dir)
    texts = [text for text, _ in ctx_texts(ctx_rows, tokenizer)]
    values, diagnostics = encode_texts(texts, tokenizer, model, device, CTX_LIMIT, batch_size)
    if diagnostics["truncated_unique"]:
        raise ValueError("CTX exceeded its token budget before the tokenizer")
    return values


def encode_teacher(texts, device="cuda", batch_size=32, cache_dir=None):
    """BGE vectors of the distinct non-empty teacher texts: (unique texts, float32 (n, 384))."""
    torch = _deterministic_torch(device)
    from sentence_transformers import SentenceTransformer
    spec = MODELS["bge-small-en-v1.5"]
    model = SentenceTransformer(spec["repo_id"], revision=spec["revision"], device=device, cache_folder=cache_dir,
                                model_kwargs={"torch_dtype": torch.float32, "attn_implementation": "eager"})
    model.eval()
    model.requires_grad_(False)
    unique = sorted({t for t in texts if t})
    lengths = [len(model.tokenizer.encode(s, add_special_tokens=True, truncation=False)) for s in unique]
    if lengths and max(lengths) > model.max_seq_length:
        raise ValueError("Teacher text exceeds the BGE maximum length")
    if not unique:
        return unique, np.zeros((0, spec["dimension"]), dtype=np.float32)
    values = model.encode(unique, batch_size=batch_size, show_progress_bar=False, convert_to_numpy=True,
                          normalize_embeddings=True).astype(np.float32)
    return unique, values
