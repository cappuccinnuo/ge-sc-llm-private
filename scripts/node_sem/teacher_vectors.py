"""Pure teacher-vector scatter and provenance checks, shared by encoder tests."""
import hashlib
import numpy as np


def scatter(rows, unique, vectors, dimension=384):
    vectors=np.asarray(vectors)
    if vectors.dtype!=np.float32 or vectors.shape!=(len(unique),dimension) or not np.isfinite(vectors).all():
        raise ValueError("Teacher vector shape/dtype/nonfinite")
    if len(set(unique))!=len(unique):raise ValueError("Duplicate unique text")
    if len(vectors) and not np.allclose(np.linalg.norm(vectors,axis=1),1,atol=1e-5,rtol=0):
        raise ValueError("Teacher vectors not normalized")
    lookup={s:i for i,s in enumerate(unique)}
    values=np.zeros((len(rows),dimension),dtype=np.float32)
    identities=[];seen=set()
    for i,row in enumerate(rows):
        key=row["row_key"]
        if key in seen:raise ValueError("Duplicate teacher row")
        seen.add(key)
        if type(row["present"]) is not bool or bool(row["text"])!=row["present"]:
            raise ValueError("Teacher text/presence mismatch")
        if row["text_sha256"]!=hashlib.sha256(row["text"].encode("utf8")).hexdigest():
            raise ValueError("Teacher text SHA differs")
        if row["present"]:values[i]=vectors[lookup[row["text"]]]
        item={k:row[k] for k in ("row_key","file","node_type","source_sha256","code_sha256","present")}
        item.update(unverified=row["unverified"],vector_sha256=hashlib.sha256(values[i].tobytes()).hexdigest())
        identities.append(item)
    return values,identities
