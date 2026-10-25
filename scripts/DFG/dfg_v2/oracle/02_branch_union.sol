pragma solidity 0.5.17;
contract BranchUnion {
    function run() public pure returns (uint) {
        uint x = 0;
        bool choose = true;
        if (choose) { x = 11; } else { x = 22; }
        uint merged = x;
        return merged;
    }
}
