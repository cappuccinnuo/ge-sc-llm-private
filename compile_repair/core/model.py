"""CP0 data records; no selection, execution or persistence logic."""
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Compiler:
    version: str
    path: str
    sha256: str


@dataclass(frozen=True)
class Compilation:
    source_path: str
    source_sha256: str
    compiler: Compiler
    command: List[str]
    cwd: str
    returncode: Optional[int]
    error_first_line: Optional[str]
    stderr: str
    stdout_sha256: str
    elapsed_seconds: float
    timed_out: bool
    cost_usd: float = 0.0
    settings: Tuple[str, ...] = ()
