


import os
import re
import subprocess

BUG_TYPES = (
    "access_control",
    "arithmetic",
    "denial_of_service",
    "front_running",
    "reentrancy",
    "time_manipulation",
    "unchecked_low_level_calls",
)

ROOT = "./experiments/ge-sc-data/source_code"
SUBDIR = "source_files"  # change to "cleaned_buggy_curated" if that's your working set
DEFAULT_VERSION = "0.4.25"

pattern = re.compile(r"pragma solidity\s*(?:\^|>=|<=|~)?\s*(\d+\.\d+\.\d+)")


def get_solc_version(source):
    with open(source, "r", encoding="utf8", errors="ignore") as f:
        content = f.read()
    matches = pattern.findall(content)
    return matches[0] if matches else DEFAULT_VERSION


def collect_smart_contracts():
    files = []
    for bug in BUG_TYPES:
        source_dir = os.path.join(ROOT, bug, SUBDIR)
        if not os.path.isdir(source_dir):
            print(f"[skip] missing dir: {source_dir}")
            continue
        files += [
            os.path.join(source_dir, f)
            for f in os.listdir(source_dir)
            if f.endswith(".sol")
        ]
    return files


def main():
    smart_contracts = collect_smart_contracts()
    print(f"Found {len(smart_contracts)} .sol files across {len(BUG_TYPES)} bug types")

    versions_needed = {}
    for sc in smart_contracts:
        v = get_solc_version(sc)
        versions_needed.setdefault(v, []).append(sc)

    print(f"Distinct solc versions required: {sorted(versions_needed)}")

    installed = 0
    failed = []
    for version, files in sorted(versions_needed.items()):
        print(f"Installing solc {version} ({len(files)} contracts need it)")
        try:
            subprocess.run(["solc-select", "install", version], check=True)
            installed += 1
        except subprocess.CalledProcessError as e:
            print(f"  failed: {e}")
            failed.append(version)

    print(f"Installed {installed}/{len(versions_needed)} solc versions")
    if failed:
        print(f"Failed versions: {failed}")


if __name__ == "__main__":
    main()
