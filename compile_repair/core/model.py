"""PROMPTS 4.3 core records: data only, with byte ranges in current-copy coordinates."""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


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


@dataclass(frozen=True)
class SourceFile:
    path: str
    sha256: str
    content: bytes
    kind: str = "file"


@dataclass(frozen=True)
class CompilationUnit:
    unit_id: str
    sources: Tuple[SourceFile, ...]
    known_version: Optional[str] = None
    regression: Optional[str] = None


@dataclass(frozen=True)
class Patch:
    start: int
    end: int
    expected: bytes
    replacement: bytes
    step: str
    round: int = 1
    reason: str = ""


@dataclass(frozen=True)
class Change:
    start: int
    end: int
    old: bytes
    new: bytes
    step: str
    round: int
    reason: str


@dataclass(frozen=True)
class Segment:
    new_start: int
    new_end: int
    original_start: Optional[int]
    original_end: Optional[int]
    kind: str


@dataclass(frozen=True)
class Provenance:
    original_sha256: str
    result_sha256: str
    original_length: int
    result_length: int
    level: str
    changes: Tuple[Change, ...]
    segments: Tuple[Segment, ...]


@dataclass(frozen=True)
class EnvironmentPlan:
    interval: Optional[Tuple[Tuple[int, ...], Tuple[int, ...]]]
    effective_interval: Tuple[Tuple[int, ...], Tuple[int, ...]]
    origin: str
    groups: Tuple[Tuple[str, ...], ...]
    priority: Optional[str]
    flags: Tuple[str, ...]
    inference: Tuple[Dict[str, Any], ...] = ()
    override: bool = False


@dataclass
class ManifestRecord:
    unit_id: str
    inputs: List[Dict[str, Any]]
    status: str
    reason: Optional[str]
    plan: Optional[EnvironmentPlan]
    selected_version: Optional[str]
    settings: Tuple[str, ...]
    flags: List[str]
    attempts: List[Dict[str, Any]]
    provenance: Dict[str, Provenance]
    llm_calls: int = 0
    cost_usd: float = 0.0
