pragma solidity 0.8.24;
contract Lock {
    function enter() public {
        assembly {
            if tload(0) { revert(0, 0) }
            tstore(0, 1)
        }
        assembly { tstore(0, 0) }
    }
}
