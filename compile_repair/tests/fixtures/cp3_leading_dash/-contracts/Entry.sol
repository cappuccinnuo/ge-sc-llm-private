pragma solidity >=0.4.12;
import "../lib/Dependency.sol";

contract Entry {
    Dependency dependency;

    function callDependency(Dependency target) public returns (uint) {
        return target.value();
    }
}
