pragma solidity >=0.4.24 <=0.5.11;
contract CompositeStateWrites {
    struct Inner { uint g; }
    struct S { uint f; Inner inner; }
    S s;
    mapping(uint => S) m;
    S[] arr;
    mapping(uint => uint) scalar;
    function direct(uint v) public { s.f = v; }
    function mapped(uint k, uint v) public { m[k].f = v; }
    function arrayWrite(uint i, uint v) public { arr[i].f = v; }
    function nested(uint v) public { s.inner.g = v; }
    function mappingControl(uint k, uint v) public { scalar[k] = v; }
    function deleteControl(uint k) public { delete scalar[k]; }
}
