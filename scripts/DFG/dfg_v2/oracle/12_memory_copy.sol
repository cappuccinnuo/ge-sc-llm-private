pragma solidity 0.5.17;
contract MemoryCopy {
    struct Box { uint left; uint right; }
    Box stored;
    function run() public view returns (uint) {
        Box memory copied = stored;
        copied.left = 8;
        uint answer = copied.right;
        return answer;
    }
}
