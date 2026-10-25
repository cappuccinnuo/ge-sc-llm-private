pragma solidity 0.5.11;
contract MemoryArray {
    function write(uint i, uint v) public pure returns (uint) {
        uint[] memory a = new uint[](3);
        a[i] = v;
        return a[i];
    }
}
