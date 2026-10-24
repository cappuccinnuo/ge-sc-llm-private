"""Immutable L1 events extending the frozen scalar event contract."""
from dataclasses import dataclass
from typing import Tuple

from ..models import Span


@dataclass(frozen=True)
class V2Event:
    id: str
    function: str
    anchor: Span
    reads: Tuple[str, ...] = ()
    writes: Tuple[str, ...] = ()
    weak_writes: Tuple[str, ...] = ()
    kind: str = "expression"
