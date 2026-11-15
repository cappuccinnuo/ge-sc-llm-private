pragma solidity 0.4.10; contract A {
  uint x;
  function f(uint v) public { if (v > 1) { x = v; } }
}
