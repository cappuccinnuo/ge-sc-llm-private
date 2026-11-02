"""NodeSem v1: node feature adapters outside the frozen DFG implementation."""

VERSION = "nodesem-v1"
TOKEN_IDS = "token_ids"
CODE = "code"
CTX = "ctx"
STATIC = "static"
STUDENT = "student"
TEACHER = "teacher"
TEACHER_JUDGE = "teacher_judge"
ANON = "anonymous"
ORIG = "original"

MODALITIES = (TOKEN_IDS, CODE, CTX, STATIC, STUDENT, TEACHER, TEACHER_JUDGE)
VIEWS = (ANON, ORIG)

# Only model/fit-path modules enter an execution seal. Feature producers bind
# their implementation SHA in feature manifests; diagnostics are not trainers.
RUNTIME_MODULES = (
    "__init__.py", "feature_spec.py", "carrier.py", "adapter.py",
    "model.py", "init.py", "checkpoint_io.py", "execution.py",
)
