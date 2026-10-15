"""Stage H2: reserved E3a fits only; immutable H1/G references."""
from pathlib import Path
from scripts.DFG.experiments.e23_cv.prepare import DEFAULT_OUTPUT as H1
from scripts.DFG.experiments.e23_pilot.inputs import ROOT
BATCH_VERSION = "stage-h2-e3a-paper-kfold-v1"
DEFAULT_OUTPUT = ROOT / "scripts/DFG/experiments/artifacts/paper_kfold/stage_h2_v1"
