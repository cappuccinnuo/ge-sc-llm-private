"""Exact prior epoch/optimizer/early-stop loop with new audit and binding handlers."""
from scripts.DFG.experiments.e23_pilot import training as old
from .model import adapt,FORWARD_RELATIONS
from .runtime import gradient_audit
from .checkpoint import save_checkpoint,restore_checkpoint
FIT=adapt(old.FIT,gradient_audit=gradient_audit,save_checkpoint=save_checkpoint,
          restore_checkpoint=restore_checkpoint)
fit=adapt(old.fit,FIT=FIT,FORWARD_RELATIONS=FORWARD_RELATIONS)
assert FIT.__code__ is old.FIT.__code__ and fit.__code__ is old.fit.__code__
