pragma solidity >=0.4.24;
contract A {
  uint[][] s;
  function f(uint[][] memory m) public { s = m; }
}
