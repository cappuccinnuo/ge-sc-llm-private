"""Source identities, analysis-only events, and explicit incomplete outcomes."""
from dataclasses import dataclass, field
from typing import Tuple
from ..models import Span

@dataclass(frozen=True)
class DeclarationRef:
    id: str
    source_sha256: str
    unit: str
    contract: Span
    declaration: Span
    name: str
    type_name: str
    kind: str
    key_type: str = ""

@dataclass(frozen=True)
class StateLocation:
    id: str
    root: DeclarationRef
    key_kind: str
    key_value: str
    key_type: str
    certainty: str
    evidence: Tuple[str, ...] = ()

@dataclass(frozen=True)
class StateEvent:
    id: str
    function: str
    block: str
    scalar_event: str
    anchor: Span
    expression: Span
    kind: str
    location: object = None
    detail: str = ""

StateReadEvent = StateEvent
StateWriteEvent = StateEvent

@dataclass
class StateFunctionIR:
    base: object
    events: dict
    locations: dict
    declarations: dict

@dataclass(frozen=True)
class StateFact:
    definition: StateEvent
    use: StateEvent
    location_id: str
    certainty: str
    cfg_witness: Tuple[str, ...]
    path_status: str = "cfg_reachable_path_conditions_not_solved"

@dataclass
class StateAccessSummary:
    function: str
    events: list = field(default_factory=list)
    environment_reads: list = field(default_factory=list)
    completeness: str = "supported_subset"

@dataclass
class StateAnalysisResult:
    function: str
    status: str
    ir: object = None
    facts: list = field(default_factory=list)
    unknown_reads: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)
    iterations: int = 0
    reachable: set = field(default_factory=set)
