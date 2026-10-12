"""Print diagnosis.json as compact tables."""
import json
from pathlib import Path

data = json.loads((Path(__file__).with_name("diagnosis.json")).read_text())
print(f"{'experiment':58s} {'ctr':>4s} {'nodes':>6s} {'pos':>5s} {'%SolidiFI':>9s} {'%seen':>6s} | "
      f"{'HGT':>6s} {'lookup':>6s} {'marker':>6s} | {'HGT SolidiFI':>12s} {'HGT SmartBugs (pos)':>20s}")
for name, entry in data.items():
    for key, r in entry.items():
        if not key.startswith("line"):
            continue
        f = r["fold_mean_buggy_f1"]
        sb = r["hgt"]["smartbugs_files"]
        print(f"{name + ' | ' + key:58s} {r['contracts']:4d} {r['nodes']:6d} {r['positives']:5d} "
              f"{r['positives_in_solidifi_files_percent']:9.2f} {r['held_out_positives_seen_as_training_positive_percent']:6.2f} | "
              f"{f['hgt']:6.2f} {f['lookup']:6.2f} {f['marker']:6.2f} | {r['hgt']['solidifi_files']['buggy_f1']:12.2f} "
              f"{sb['buggy_f1']:14.2f} ({sb['positives']})")
print()
for name, entry in data.items():
    c = entry["contract"]
    print(f"{name:32s} contract: HGT {c['hgt_pooled_buggy_f1']:6.2f}  marker rule {c['marker_rule_buggy_f1']:6.2f}  "
          f"SolidiFI {c['hgt_correct_on_solidifi']}  SmartBugs {c['hgt_correct_on_smartbugs']}  clean {c['hgt_correct_on_clean']}")
