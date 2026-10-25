pragma solidity 0.5.17;
contract ForUpdate {
    function run() public pure returns (uint) {
        uint i = 0;
        for (; i < 3; i++) { uint snapshot = i; }
        return i;
    }
}
