"""Archive complete JSONL streams without replacing their local originals."""
import gzip
import shutil
from batch import OUT, load, save, sha


def main():
    references = {"sample_receipts.jsonl":load("execution.json")["receipt_sha256"],
                  "inverse_scores.jsonl":load("inverse_acceptance.json")["scores_sha256"],
                  "inverse_graphs.jsonl":load("inverse_acceptance.json")["graphs_sha256"]}
    inventory={}
    for name, digest in references.items():
        source=OUT/name
        assert sha(source.read_bytes())==digest
        path=source.with_suffix(".jsonl.gz")
        with source.open("rb") as raw, path.open("xb") as file:
            with gzip.GzipFile(filename="",fileobj=file,mode="wb",mtime=0) as archive:
                shutil.copyfileobj(raw,archive)
        with gzip.open(path,"rb") as stored:
            assert sha(stored.read())==digest
        inventory[path.name]=dict(uncompressed_sha256=digest,sha256=sha(path.read_bytes()),
                                  bytes=path.stat().st_size,uncompressed_bytes=source.stat().st_size)
    save("archives.json",inventory)


if __name__=="__main__":
    main()
