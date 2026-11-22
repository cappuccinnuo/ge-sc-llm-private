"""Pin the reviewed implementation and earlier evidence before CP4.1 measurement."""
from batch import *
from compile_repair.toolchain.slither import check_profile
from compile_repair.toolchain.solc import load_trusted_compilers

LOCAL.mkdir(parents=True,exist_ok=True)
cp4=json.loads(frozen(OLD/"seal.json"))
for name,r in cp4["artifacts"].items():
    checked(OLD/name,r["sha256"])
refs={}
for p in [ROOT/"compile_repair/PROMPTS.md",ART/"cp3_2_v1/seal.json",ART/"cp3_2_v1/unit_attributions.jsonl.gz",
          OLD/"seal.json",ART/"cp4_review_v1/README.md",ART/"cp4_review_v1/probe_operator_messages.json"]:
    refs[str(p.relative_to(ROOT))]=sha(frozen(p))
profile=check_profile("production");compilers,versions,trust=load_trusted_compilers()
from compile_repair.toolchain.solc import version_tuple
coverage=json.loads(frozen(ART/"cp0_1_compilers_v1/coverage.json"))
assert len(compilers)==coverage["total_installed_including_legacy_controls"]
compilers={v:c for v,c in compilers.items() if (0,4,12)<=version_tuple(v)<=version_tuple(coverage["latest_release_in_snapshot"])}
assert len(compilers)==coverage["supported_installed"]==92
saved("baseline.json",dict(base_commit=BASE,inputs=refs,cp4_sealed_files=len(cp4["artifacts"]),profile=profile,
     compiler_sha256={v:c.sha256 for v,c in compilers.items()},compiler_trust=trust,external=str(LOCAL),
     previous_production=cp4["implementation"],cost_usd=0))
