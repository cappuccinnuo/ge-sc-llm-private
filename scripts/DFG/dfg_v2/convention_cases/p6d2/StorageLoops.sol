pragma solidity >=0.4.24 <=0.5.11;
contract StorageLoops {
    uint[] arr;
    struct S { uint x; }
    mapping(uint => S) m;
    function arrayLoop(uint n, uint v) public {
        for (uint i = 0; i < n; i++) { arr[i] = v; }
    }
    function referenceLoop(uint k, uint n) public {
        S storage p = m[k];
        while (p.x < n) { p.x += 1; }
    }
}
