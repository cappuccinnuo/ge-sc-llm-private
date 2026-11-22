pragma solidity >=0.4.24;
contract A {
  struct S { uint[] a; }
  S[] s;
  function f() public { S[] memory m = new S[](1); s = m; }
}
