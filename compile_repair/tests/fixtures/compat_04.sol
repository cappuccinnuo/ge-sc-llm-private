// CP0 compatibility probe; no network or deployed-chain interaction.
// try/catch: Solidity v0.6.0 breaking changes; unchecked: v0.8.0 breaking changes.
pragma solidity >=0.4.0 <0.5.0;
contract Sink { function ping(uint x) public returns (uint); }
contract Base {
    uint public value;
    modifier gate() { _; }
    function bump(uint x) internal returns (uint) { value += x; return value; }
}
contract Probe is Base {
    event Seen(uint value);
    function run(uint x, Sink sink) public gate returns (uint) {
        uint y = bump(x);
        Seen(y);
        return sink.ping(y);
    }
}
