"""Small shared helpers."""
import hashlib
import json




# ----------------------------------------------------------------------
# experiments/common (picked: digest)
def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
