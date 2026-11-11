"""Hard-condition negative tests for the EP6 prerequisite delta."""
import numpy as np
import pytest
from scripts.edge_sem.recon.ep6_prereq import strict_delta

@pytest.mark.parametrize("bit,direction,eligible,relation", [
    (20,1,True,"DATA_DEF_USE"),(23,-1,True,"DATA_DEF_USE"),
    (23,1,False,"DATA_DEF_USE"),(23,1,True,"READS_STATE")])
def test_reject_unauthorized_changes(bit,direction,eligible,relation):
    a=np.zeros((1,74),dtype=np.uint8);b=a.copy()
    if direction<0:a[0,bit]=1
    else:b[0,bit]=1
    with pytest.raises(ValueError):
        strict_delta(["x"],a,["x"],b,{"x"} if eligible else set(),[relation])

def test_allowed_sink_bits_and_order_gate():
    a=np.zeros((1,74),dtype=np.uint8);b=a.copy();b[0,[22,23,37,39]]=1
    assert strict_delta(["x"],a,["x"],b,{"x"},["DATA_DEF_USE"])["changed_bits"]==4
    with pytest.raises(ValueError):strict_delta(["x"],a,["y"],b,{"x"},["DATA_DEF_USE"])
