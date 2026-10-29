# Prompt 8D 完整推理汇总独立验收

状态：通过。验收无模型前向、无训练。

300份结果/状态及SHA完整；orig/C1标签和source/fold身份一致。独立从预测重算3600逐折、360 pooled、240折均值、1980变化表、1200逐折配对、120 pooled配对和80配对均值。

配对方向为B_full−8C_idN、C_matched−B_matched；两种标签/三种cohort不混用。非SolidiFI逐节点分类和float32概率完全不变；不输出非SolidiFI折均值。

report_facts 状态：checked。详细SHA与逐项检查见review.json。该验收验证统计与身份，不证明诊断差异具有纯因果解释。
