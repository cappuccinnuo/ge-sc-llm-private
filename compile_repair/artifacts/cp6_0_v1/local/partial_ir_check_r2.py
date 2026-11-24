"""CP6.0.1 rerun of the four partial-IR units with the unchanged Codex runner, into a new output folder."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import partial_ir_check  # noqa: E402

partial_ir_check.OUT = partial_ir_check.ROOT.parent / "compile-repair-local/cp6_0_1_v1"
partial_ir_check.OUT.mkdir(parents=True, exist_ok=False)
sys.exit(partial_ir_check.main())
