pragma solidity 0.4.26;
contract EnvironmentSynonyms {
    function run() public view returns (uint) {
        uint firstTime = now;
        uint secondTime = block.timestamp;
        uint remaining = msg.gas + gasleft();
        uint held = this.balance + address(this).balance;
        return firstTime + secondTime + remaining + held;
    }
}
