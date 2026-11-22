pragma solidity >=0.5.0;
pragma experimental ABIEncoderV2;
contract A {
  struct S { uint a; }
  S[] s;
  function f(S[] memory m) public { s = m; }
}
