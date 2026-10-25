pragma solidity 0.5.17;
contract StructWeakWrite {
    struct Pair { uint left; uint right; }
    function run() public pure returns (uint) {
        Pair memory p = Pair(1, 2);
        p.left = 3;
        uint observed = p.right;
        return observed;
    }
}
