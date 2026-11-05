"""Configuration exposes implemented capabilities only."""
from dataclasses import dataclass

@dataclass(frozen=True)
class DDGConfig:
    use_ddg: bool = True
    add_scalar: bool = False
    state_mode: str = "orders"
    recovery: str = "modifiers"
    max_iterations: int = 100000
    def __post_init__(self):
        if self.state_mode not in ("off", "def_use", "orders"):
            raise ValueError("state_mode must be off, def_use or orders")
        if self.recovery not in ("frozen", "inheritance", "modifiers"):
            raise ValueError("Unsupported recovery level")
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be positive")
