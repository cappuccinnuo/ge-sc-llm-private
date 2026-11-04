"""Reuse numerical/result checks; only the batch identity changes."""
from scripts.DFG.experiments.overall_cv import checks as prior
from .common import *
from .model import adapt
check_initial=adapt(prior.check_initial,PAIR_VERSION=PAIR_VERSION)
completed=adapt(prior.completed,job_dir=job_dir)
