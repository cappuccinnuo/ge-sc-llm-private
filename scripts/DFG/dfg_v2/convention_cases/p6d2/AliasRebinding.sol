pragma solidity >=0.4.24 <=0.5.11;
contract AliasRebinding {
    struct Box { uint value; }
    Box first;
    Box second;
    uint seeded = 7;
    function declarations(uint input) public returns (uint named) {
        uint local;
        uint assigned = input;
        named = assigned;
        return local + named;
    }
    function readMember() public view returns (uint) {
        Box storage ref = first;
        return ref.value;
    }
    function compoundMember() public {
        Box storage ref = first;
        ref.value += 1;
    }
    function directControl() public { first.value = 7; }
    function firstAlias() public {
        Box storage ref = first;
        ref.value = 7;
    }
    function rebindAlias() public {
        Box storage ref = first;
        ref = second;
        ref.value = 7;
    }
}
