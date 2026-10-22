"""Exact old epoch loop and resource wrapper, with only overall checkpoint bindings."""
from types import FunctionType
from scripts.DFG.experiments.e23_pilot import training as old
from .checkpoint import save_checkpoint,restore_checkpoint
FIT=FunctionType(old.FIT.__code__,dict(old.FIT.__globals__,save_checkpoint=save_checkpoint,
                restore_checkpoint=restore_checkpoint),old.FIT.__name__,old.FIT.__defaults__,old.FIT.__closure__)
fit=FunctionType(old.fit.__code__,dict(old.fit.__globals__,FIT=FIT),
                 old.fit.__name__,old.fit.__defaults__,old.fit.__closure__)
assert fit.__code__ is old.fit.__code__ and FIT.__code__ is old.FIT.__code__
