pragma solidity ^0.8.0;
import {C as A} from "./A.sol"; import {C as B} from "./B.sol";
contract Main {
    function viaCast(address x, address y) public view returns (uint) { return A(x).f() + B(y).f(); }
    function viaNew() public returns (uint) { return new B().f(); }
}
