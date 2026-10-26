pragma solidity >=0.4.24 <=0.5.11;
contract ShapeSupplement {
    struct S { uint value; }
    S[9] stateRecords;
    function storageArrayLoop(uint n, uint v) public {
        S[9] storage records = stateRecords;
        for (uint i = 0; i < n; i++) { records[i] = S(v); }
    }
    function memoryBytes(uint n) public pure {
        bytes memory out = new bytes(n);
        for (uint i = 0; i < n; i++) { out[i] = bytes1(uint8(1)); }
    }
    function bare(uint x) public pure { x; }
    function unused(uint amount) public { msg.sender.call.value(amount); }
}
