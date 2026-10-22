"""Analysis-only control IR. No node in this module is an HCG/model node."""
from dataclasses import dataclass, field
from typing import Optional
from ..models import Span

RELATION = "CONTROL_DEPENDENCE"
VERSION = "guard-control-explicit-exits-v1"

@dataclass
class ControlNode:
    id: str
    kind: str
    anchor: Optional[Span] = None
    successors: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)

@dataclass
class ControlIR:
    function: str
    file: str
    source_sha256: str
    entry: str
    normal_exit: str
    exceptional_exit: str
    exit: str
    nodes: dict
    evidence: dict = field(default_factory=dict)

@dataclass(frozen=True)
class ControlFact:
    function: str
    source_sha256: str
    controller: Span
    controlled: Span
    branch: str
    cfg_edge: tuple
    cfg_path: tuple
    evidence: dict = field(default_factory=dict)
    relation: str = RELATION

@dataclass
class ControlResult:
    function: str
    status: str
    ir: Optional[ControlIR] = None
    facts: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
