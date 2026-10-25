pragma solidity 0.5.11;
contract MappingWrites {
    mapping(uint => uint) public m;
    function write(uint k, uint v) public { m[k] = v; }
    function erase(uint k) public { delete m[k]; }
    function read(uint k) public view returns (uint) { return m[k]; }
}
