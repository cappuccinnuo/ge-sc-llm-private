pragma solidity 0.5.17;
contract StateInitializer {
    uint seed = 2;
    uint derived = seed + 1;
    address creator = msg.sender;
}
