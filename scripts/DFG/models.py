"""Python 3.7-compatible immutable identities; no new model graph nodes."""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

class Unsupported(ValueError):
    """Conservative analysis fallback, never a request to remove a sample."""

@dataclass(frozen=True, order=True)
class Span:
    file: str
    start: int
    end: int
    role: str

    def __post_init__(self):
        if self.start < 0 or self.end < self.start:
            raise ValueError("Invalid half-open UTF-8 byte span")

@dataclass(frozen=True)
class Symbol:
    id: str
    name: str
    function: str
    declaration: Span
    kind: str
    type_name: str

@dataclass(frozen=True)
class Event:
    id: str
    function: str
    anchor: Span
    reads: Tuple[str, ...] = ()
    writes: Tuple[str, ...] = ()
    kind: str = "expression"

@dataclass
class Block:
    id: str
    events: List[Event] = field(default_factory=list)
    successors: Set[str] = field(default_factory=set)

@dataclass
class FunctionIR:
    id: str
    file: str
    entry: str
    blocks: Dict[str, Block]
    symbols: Dict[str, Symbol]

@dataclass(frozen=True)
class Definition:
    id: str
    symbol: str
    event: str
    function: str
    anchor: Span

@dataclass(frozen=True)
class Fact:
    symbol: str
    definition: Definition
    use: Event

@dataclass(frozen=True)
class DDGConfig:
    use_ddg: bool = False
    max_iterations: int = 100000

    def __post_init__(self):
        if type(self.use_ddg) is not bool or type(self.max_iterations) is not int or self.max_iterations < 1:
            raise ValueError("Invalid DDG configuration")

@dataclass
class AnalysisResult:
    functions: List[FunctionIR] = field(default_factory=list)
    diagnostics: List[dict] = field(default_factory=list)
