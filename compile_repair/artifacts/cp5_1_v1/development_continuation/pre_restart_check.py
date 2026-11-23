"""Check the exact reviewed Ubuntu workload before the user-authorized distribution restart."""
import datetime
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
proc = Path(r"\\wsl.localhost\Ubuntu-22.04\proc")
review = json.loads((HERE/"wsl_health_review.json").read_bytes())
grant = json.loads((HERE/"wsl_restart_authorization.json").read_bytes())
proof = HERE/"prefix_verification.json"
assert hashlib.sha256(proof.read_bytes()).hexdigest() == grant["prefix_verification_sha256"]
assert json.loads(proof.read_bytes())["rows"] == 6940
assert grant["distribution"] == "Ubuntu-22.04"
actual = {}
user_names = {}
jobs = []
for p in proc.iterdir():
    if not p.name.isdecimal():
        continue
    try:
        fields = dict(l.split(":",1) for l in (p/"status").read_text().splitlines() if ":" in l)
        name = fields["Name"].strip()
        cmdline = (p/"cmdline").read_bytes()
        if cmdline and fields["Uid"].split()[0] == "1000":
            user_names[name] = user_names.get(name,0)+1
        if name == "bash":
            values = (p/"stat").read_text().rsplit(")",1)[1].split()
            children = (p/"task"/p.name/"children").read_text().split()
            actual[int(p.name)] = (values[19],values[2],values[5],children)
        if name.startswith("solc") or any(token in cmdline for token in (
                b"/evaluate_units.py\x00",b"/resume_development.py\x00",b"/slither\x00",
                b"/pytest\x00",b"torchrun",b"train.py\x00")):
            jobs.append(p.name)
    except FileNotFoundError:
        continue
expected={r["pid"]:(r["start_ticks"],r["process_group"],r["foreground_group"],r["children"])
          for r in review["bash_shells"]}
assert len(actual)==4 and actual==expected and all(group==fg and not kids for _,group,fg,kids in actual.values())
assert user_names==review["nonempty_process_names_for_uid_1000"] and not jobs
with (HERE/"pre_restart_check.json").open("x",encoding="utf8",newline="\n") as output:
    json.dump(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),shells=sorted(actual),
                   user_workload=user_names,active_measurements=jobs,previous_boot_uptime=(proc/"uptime").read_text().strip(),
                   prior_boot_id=(proc/"sys/kernel/random/boot_id").read_text().strip(),ready=True),
              output,indent=2)
    output.write("\n")
print("4 unchanged idle bash sessions, no compiler, evaluator, training or new user process",flush=True)
