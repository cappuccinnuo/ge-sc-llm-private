pragma solidity >=0.4.24 <=0.5.11;
contract StorageAliasWrite {
    struct S { uint f; }
    mapping(uint => S) m;
    function explicitAlias(uint k, uint v) public {
        S storage p = m[k];
        p.f = v;
    }
}
