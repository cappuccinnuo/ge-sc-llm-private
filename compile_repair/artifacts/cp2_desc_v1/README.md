# CP2.2 生产降序存储（2026-11-14，修改 AI：Codex）

PROMPTS r2.10 §4.4c 第 3 节：同一 repair CLI，production profile（Slither 0.11.6、crytic-compile 0.4.2），92 个支持版本，--regression mando --order descending。846 输入，843 success、3 个已知 slither_side_failure（reentrancy_bonus、reentrancy_cross_function、reentrancy_insecure），失败不写 graph。

与 cr_store_mando_v3 比较：229 同版、614 不同版，843/843 key5 与规范化有序 IR 相同；source length 815 同、28 不同，仅诊断。完整 argv、逐份验收与版本对在 ../cp2_2_v1/descending_*。降序仅作验证，不替代升序主存储，不改 D5。

store.tar.gz 含 4,229 个成员（含 seal），SHA256 02ccc74dce4a9acde715d0d8a133d87d87345cbb9fcbba7951a3bc82d4ceb2c1，逐成员回读通过，见 ../cp2_2_v1/cp2_desc_v1_archive_audit.json；散文件保留。没有重做 CP0–CP2.1 生产运行，独立审查后再进入 CP3。
