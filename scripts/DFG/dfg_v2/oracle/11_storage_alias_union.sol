pragma solidity 0.4.26;
contract StorageAliasUnion {
    struct Box { uint value; }
    Box first;
    Box second;
    function explicitAlias() public returns (uint) {
        Box storage ref = first;
        ref = second;
        ref.value = 7;
        uint afterValue = ref.value;
        return afterValue;
    }
    function legacyAlias() public returns (uint) {
        var legacy = first;
        legacy.value = 9;
        uint observed = legacy.value;
        return observed;
    }
}
