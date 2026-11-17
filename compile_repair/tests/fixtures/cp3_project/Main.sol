pragma solidity >=0.4.12 <0.9.0;
import "./sub/Base.sol";
import "@vendor/Numbers.sol";
contract Main is Base {
    function total() public returns (uint) { return baseValue() + Numbers.value(); }
}
