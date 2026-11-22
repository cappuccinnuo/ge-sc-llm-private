"""Complete the frozen package draw with user-approved closures whose entry is in the package."""
from collections import Counter, defaultdict
from batch import *
import new_samples
import restore_scores
from new_plan import SEED, sites_for, signature
from compile_repair.evaluation.benchmark import stratified_sample
from compile_repair.toolchain.slither import check_profile
from compile_repair.toolchain.solc import load_trusted_compilers

OP = "unresolved_package_import"


def sample_key(row):
    return row["operator"], row["unit_id"]


def plan():
    authorization = load("package_sampling_authorization.json")
    checked(OUT/"package_sampling_review.json", authorization["request_sha256"])
    request = load("package_sampling_review.json")
    checked(OUT/"package_applicability_audit.json", request["audit_sha256"])
    checked(OUT/"new_plan.jsonl.gz", request["original_sample_sha256"])
    original = {r["unit_id"]: r for r in rows(OUT/"new_plan.jsonl.gz") if r["operator"] == OP}
    extra = set(request["affected_cases"])
    assert len(original) == 28 and len(extra) == 86 and not (set(original) & extra)
    frozen(OLD/"bases.jsonl.gz")
    by_corpus = defaultdict(list)
    distribution = Counter()
    for base in rows(OLD/"bases.jsonl.gz"):
        uid = base["unit_id"]
        if uid not in original and uid not in extra:
            continue
        sources, sites = sites_for(base)
        site = sites[OP]
        sig = signature(site)
        package = site[3]["package"]
        if next(iter(sources)) in site[3]["file_renames"]:
            raise ValueError("Entry selected for relocation: "+uid)
        if uid in original and (sig != original[uid]["site_sha256"] or package != original[uid]["package"]):
            raise ValueError("Original sampled edit changed: "+uid)
        row = {k:base[k] for k in ("unit_id","corpus","series","group","split")}
        by_corpus[row["corpus"]].append(dict(row, operator=OP, seed=SEED, site_sha256=sig, package=package))
        distribution[row["corpus"],package,uid in extra] += 1
    combined = []
    for corpus, items in sorted(by_corpus.items()):
        combined.extend(stratified_sample(items,200,SEED,OP))
    if {r["unit_id"] for r in combined} != set(original) | extra or len(combined) != 114:
        raise ValueError("Merged package draw differs from the authorized population")
    supplement = [r for r in combined if r["unit_id"] in extra]
    output_rows("package_union_plan.jsonl.gz",combined)
    output_rows("supplement_plan.jsonl.gz",supplement)
    saved("supplement_sampling.json",dict(original=28,added=len(supplement),union=len(combined),seed=SEED,
        cap_per_operator_corpus=200, plan_sha256=sha((OUT/"supplement_plan.jsonl.gz").read_bytes()),
        union_sha256=sha((OUT/"package_union_plan.jsonl.gz").read_bytes()),
        package_counts=[dict(corpus=c,package=p,added=a,units=n) for (c,p,a),n in sorted(distribution.items())]))
    print("package union",len(combined),"new",len(supplement),flush=True)


def setup(module):
    check_profile("production")
    trusted, module.FROZEN, _ = load_trusted_compilers()
    expected = load("baseline.json")["compiler_sha256"]
    module.COMPILERS = {v:trusted[v] for v, h in expected.items() if trusted[v].sha256 == h}
    if len(module.COMPILERS) != 92:
        raise ValueError("Compiler identities differ from the frozen snapshot")
    module.BASES = {r["unit_id"]:r for r in rows(OLD/"bases.jsonl.gz")}


def observe():
    setup(new_samples)
    spec = load("supplement_sampling.json")
    checked(OUT/"supplement_plan.jsonl.gz",spec["plan_sha256"])
    sample = list(rows(OUT/"supplement_plan.jsonl.gz"))
    counts = Counter()
    def collect():
        for result in ordered_work(new_samples.perform,sample,3):
            counts[result["outcome"]] += 1
            yield dict(result,cohort="supplement")
    output_rows("supplement_observations.jsonl.gz",collect())
    assert sum(counts.values()) == spec["added"]
    saved("supplement_execution.json",dict(profile="production",completed=sum(counts.values()),counts=counts,
        observations_sha256=sha((OUT/"supplement_observations.jsonl.gz").read_bytes())))
    print("package supplement trigger",dict(counts),flush=True)


def restore():
    setup(restore_scores)
    restore_scores.STAGE = "supplement"
    receipt = load("supplement_execution.json")
    checked(OUT/"supplement_observations.jsonl.gz",receipt["observations_sha256"])
    observed = [r for r in rows(OUT/"supplement_observations.jsonl.gz") if r["outcome"]=="included"]
    counts = Counter()
    def collect():
        for result in ordered_work(restore_scores.one, observed, 3):
            if "stop" in result:
                saved("supplement_restoration_stop.json",result)
                raise ValueError("{}: {}".format(result["unit_id"],result["reason"]))
            if "migration" not in result or not result["migration"]["exact"]:
                raise ValueError("Missing exact migrated graph: "+result["unit_id"])
            counts["exact"] += 1
            counts["normalized_exact"] += int(result["score"]["metadata_normalized"])
            counts["migration"] += 1
            counts["normalized_migration"] += int(result["migration"]["metadata_normalized"])
            yield result
    output_rows("supplement_scores.jsonl.gz",collect())
    assert counts["exact"] == counts["migration"] == len(observed)
    saved("supplement_score_acceptance.json",dict(expected=len(observed),counts=counts,passed=True,
        scores_sha256=sha((OUT/"supplement_scores.jsonl.gz").read_bytes()),new_compilations=True))
    print("package supplement restorations",dict(counts),flush=True)


if __name__ == "__main__":
    plan()
    observe()
    restore()
