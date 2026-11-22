pragma solidity 0.6.12;
import "./Child.sol";
contract Factory {
    function make() public returns (Child) { return new Child(); }
    function creation() public pure returns (bytes memory) { return type(Child).creationCode; }
}
