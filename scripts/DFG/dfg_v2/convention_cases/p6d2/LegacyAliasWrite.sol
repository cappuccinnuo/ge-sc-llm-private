pragma solidity 0.4.24;
contract LegacyAliasWrite {
    struct S { uint f; }
    mapping(uint => S) m;
    function legacyAlias(uint k, uint v) public {
        var p = m[k];
        p.f = v;
    }
}
