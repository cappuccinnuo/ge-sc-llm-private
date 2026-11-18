pragma solidity ^0.8.0;
import {C as A} from "./A.sol"; import {C as B} from "./B.sol";
contract Main { function useBoth(A a, B b) public view returns(uint) { return a.f()+b.f(); } }
