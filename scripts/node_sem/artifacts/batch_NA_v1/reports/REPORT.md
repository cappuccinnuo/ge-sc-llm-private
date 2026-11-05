# NS-P5A N-A results

本批为本机 RTX3050、默认 TF32 的原名视图实验，240/240 正式拟合通过验收。
最终服务器实验另行封存并按同一预先登记复现；两批不合并、不择优，结论不一致时都报告。

| Task | Graph / configuration | Best BF1 mean | Sample SD |
|---|---|---:|---:|
| access_control_contract | G0/S0o | 90.1781 | 6.3092 |
| access_control_contract | G0/S1o | 91.1359 | 2.9445 |
| access_control_contract | G0/S2 | 89.7036 | 4.7122 |
| access_control_contract | G0/S4 | 92.2245 | 3.3468 |
| access_control_contract | G3R/S0o | 91.8961 | 6.2196 |
| access_control_contract | G3R/S1o | 92.8750 | 2.3710 |
| access_control_contract | G3R/S2 | 92.9578 | 2.4789 |
| access_control_contract | G3R/S4 | 92.2245 | 3.3468 |
| access_control_node | G0/S0o | 99.3753 | 0.3460 |
| access_control_node | G0/S1o | 99.5401 | 0.2716 |
| access_control_node | G0/S2 | 99.2319 | 1.2344 |
| access_control_node | G0/S4 | 99.6358 | 0.2673 |
| access_control_node | G3R/S0o | 99.4998 | 0.2182 |
| access_control_node | G3R/S1o | 99.5388 | 0.2543 |
| access_control_node | G3R/S2 | 99.5595 | 0.2334 |
| access_control_node | G3R/S4 | 99.5074 | 0.3519 |
| reentrancy_contract | G0/S0o | 95.1016 | 5.2643 |
| reentrancy_contract | G0/S1o | 95.9080 | 1.4393 |
| reentrancy_contract | G0/S2 | 97.8818 | 3.1811 |
| reentrancy_contract | G0/S4 | 97.1921 | 2.9741 |
| reentrancy_contract | G3R/S0o | 94.9188 | 4.2129 |
| reentrancy_contract | G3R/S1o | 97.2414 | 1.5421 |
| reentrancy_contract | G3R/S2 | 97.2348 | 1.5550 |
| reentrancy_contract | G3R/S4 | 96.5977 | 2.3579 |
| reentrancy_node | G0/S0o | 99.4203 | 0.3418 |
| reentrancy_node | G0/S1o | 99.3952 | 0.4974 |
| reentrancy_node | G0/S2 | 99.7162 | 0.2609 |
| reentrancy_node | G0/S4 | 99.7435 | 0.2145 |
| reentrancy_node | G3R/S0o | 99.6247 | 0.2818 |
| reentrancy_node | G3R/S1o | 99.7894 | 0.2299 |
| reentrancy_node | G3R/S2 | 99.8265 | 0.1151 |
| reentrancy_node | G3R/S4 | 99.7721 | 0.1885 |

S*（只用 inner_val，参考项）：S2

主终点为重入节点 G3R、S4−S0o；best 按最低 inner_val loss 选择，outer_test 仅在拟合后评分。
best/last、折均值/pooled OOF、原标签辅助结果分别报告。Wilson 区间仅用于 Precision/Recall。
详见 report.json、paired.csv、nonSolidifi_nodes.csv、errors.csv 和注意力验收索引。
