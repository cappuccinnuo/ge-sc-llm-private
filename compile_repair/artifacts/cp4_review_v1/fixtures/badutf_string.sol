pragma solidity >=0.4.24;
contract A {
  function f() public pure returns (string memory) { return "cafÿ"; }
}
