# NS-P0：只读侦察与接入点核实

日期：2026-11-01；实施与审查：Codex。输入分支 node-sem，HEAD 489cebe29181bddbd9fa6170fc4498f082fc9ac7。

已阅读PROMPTS第1—4节、5.1共享上下文和NS-P0；开始时fast-forward pull返回Already up to date。PROMPTS SHA：7c8464b102df5b55b26992d070ba51b5c1ff171c3418003483893b43ea96be04

**NS-P0完成：A/B/C接口成立。尚未实现NodeSem特征、Adapter、执行器或正式训练。** 仅新增5份只读侦察脚本、RECON.md/recon.json，并追加三份记录；既有DFG/HGT/tokenizer、图、标签、特征、初值、折、plan/seal均保持。

## 1. 输入与60份历史结果

证据：recon/inputs.py；recon.json → sections.inputs。2137个不同文件SHA核验通过，60份G0/G3R收据精确覆盖30折×2剖面，产物、prepared初值、配置和绑定一致。

- plan：/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1/plan.json
- plan SHA：cb8daf22ed9fb9cd81fe575548d338408a5420f62e7a6da529d402c148eb8a2c
- seal SHA：bd43c31ed0bec7a013524d088220378ca23bbf202e72917a18a8bcbdfbfa79fb

|任务|文件|组|折|成功收据|
|---|---:|---:|---:|---:|
|重入合约|142|124|5|10|
|重入节点|71|57|10|20|
|访问控制合约|114|107|5|10|
|访问控制节点|57|52|10|20|

8G original/anonymous特征NPZ的行身份、有限float32和逐行向量SHA一致；匿名引用与8H相同。256个源码身份的原拼写→vN双射通过。完整attempt/receipt/initial路径、SHA及state_sha256在sections.inputs.receipts；四任务配置与输入引用见第9节。

初值文件SHA、静态ZIP头untrained_initial/optimizer_steps=0、任务/折/seed/profile/fit_seed，以及prepared—initialization_ref—binding的state_sha256一致。**未独立重算初值tensor digest**：自动审批拒绝torch.load，理由是不可信pickle可能执行代码；随后仅用文件SHA和非执行zipfile/pickletools头读取，没有绕过拒绝。可确认既有已验收结果的引用一致，不能称本轮已重载60个模型。

## 2. CPU载体接入

证据：recon/carrier_probe.py，sections.carrier。小fixture和真实重入节点G3R均检查；真实图12,036原节点+187环境节点、23,703保存边。先装配8H匿名512维，再仅在深拷贝上使用固定随机float32[600]。

|探针|结果|
|---|---|
|A 512→600|inside_token构造、注册成功；原图不变|
|B 替换17个Linear(600,128)|runtime注册、build_binding、validate_binding通过；篡改临时manifest被拒绝|
|C G0 layers=0|节点/合约前向反向、有限梯度与gradient_audit通过；独立零层公式逐位相同|

- 512维：构造8.462s，参数5,111,012。

- 600维：构造9.494s，参数5,302,500。

参数增量191,488=17×88×128。计时为单次CPU记录，不是稳定性能基准。A/B未执行真实600维HGT前向；C使用小fixture。参数值和原图指纹不变，0优化器更新、0次fit、无GPU。临时JSON/NPZ位于WSL /tmp并自动删除，仅证明SHA/注册接口，不是正式NodeSem计划或checkpoint重载；普通Linear也不是完整NodeSemAdapter。

关键源码逐行证据（完整引用在JSON）：

- scripts/DFG/dfg_v2/model.py，SHA 3f77f5ae056059a1a7f4414bb137b0d300adf51bdd70d1f57a91f296fddf0644
  - L74: def _features(model):
  - L82: def _construct(model, task, graph_or_path, profile, device, node_feature,
  - L130: model.in_size = list(features.values())[0].shape[-1]
  - L132: if features[typ].ndim != 2 or features[typ].shape[1] != model.in_size:
  - L141: model.adapt_ws = nn.ModuleList([nn.Linear(model.in_size, hidden_size) for _ in model.ntypes_dict])
  - L173: def validate_registration(model, expected_schema=None, deep=True):
  - L203: if actual.requires_grad or actual.dtype != features[typ].dtype or not torch.equal(actual.cpu(), features[typ].cpu()):

- sco_models/model_hgt.py，SHA 4e6ff0710b345ffddb555810fadb74225dcf396f90b3cdf928f4f0afc3a12947
  - L166: h[ntype] = F.gelu(self.adapt_ws[n_id](G.nodes[ntype].data['inp']))
  - L393: h[ntype] = F.gelu(self.adapt_ws[n_id](symmetrical_global_graph.nodes[ntype].data['inp']))
  - L420: def forward(self):
  - L425: h[ntype] = F.gelu(self.adapt_ws[n_id](self.symmetrical_global_graph.nodes[ntype].data['inp']))
  - L590: def forward(self, batched_g_name, save_featrues=None):
  - L595: h[ntype] = F.gelu(self.adapt_ws[n_id](self.symmetrical_global_graph.nodes[ntype].data['inp']))
  - L620: h[ntype] = F.gelu(self.adapt_ws[n_id](self.symmetrical_global_graph.nodes[ntype].data['inp']))

model.py:74–79读token；130按实际宽度设in_size；141建adapt_ws；203比较注册inp和图特征。作者节点/合约forward在425/595使用adapt_ws。0层保留适配层、池化/分类头。未来配置回退必须区分None和0，不能用layers or default。

## 3. 文本、AST与函数

证据：recon/text_ast.py；sections.text_ast.tasks保存类型计数、最多10个/类型样本、源码SHA、code引号和整子树比对。

|任务|匿名代码/原节点|普通Projector|函数总数（含无体）|含体|词法归一化去重|注释|
|---|---:|---:|---:|---:|---:|---:|
|重入合约|18312/18312|17080|4035|3569|1273|4299|
|重入节点|12036/12036|10977|2283|2101|604|2249|
|访问控制合约|13432/13432|13069|3761|3306|1138|2848|
|访问控制节点|7710/7710|7495|2206|2019|593|1210|

全部匿名节点代码SHA与冻结特征一致，需求内条件/循环头/签名/合约头提取成功。while数量不足10：重入各7、访问控制各9，未补造。end_if/end_loop用synthetic_owner身份，合成else-if遵循return_if_root，输出END哨兵，不按最近行猜测。AST文本全覆盖不等于全部DDG事实可投影。

AST注释范围用空白替换，保留字节/换行/token边界；四任务ERROR/MISSING前后均0，执行token不变，字符串中的注释样式保留。这是解析检查，不是新增Solidity编译验证。

|任务|函数行数中位数|P95|最大|
|---|---:|---:|---:|
|重入合约|5.0|13.0|99|
|重入节点|6.0|13.0|99|
|访问控制合约|4.0|12.0|99|
|访问控制节点|4.0|11.75|99|

函数含modifier/constructor/fallback及无体声明，含体另列；词法去重未含状态声明上下文，不是最终LLM缓存等价类。

## 4. DFG边、拼写与环境节点

证据：sections.inputs.edges，包含每种关系node_type方向分布、属性键统计和5个实例、全部文件env_source数量和属性。

|任务|DATA_DEF_USE|READS_STATE|WRITES_STATE|ENV_FLOW|env_source|
|---|---:|---:|---:|---:|---:|
|重入合约|5710|4314|3108|3857|298|
|重入节点|3469|3070|2254|3200|187|
|访问控制合约|5773|2208|1609|2536|261|
|访问控制节点|3923|1091|767|1948|182|

DATA_DEF_USE为定义→使用；WRITES_STATE为语句→原声明；READS_STATE为声明→读取语句；ENV_FLOW为环境节点→使用处。F3保存正向事实，G3R由既有运行时生成显式反向关系，不能重复反射。

所有DATA_DEF_USE边均不直接带变量拼写，ddg_fact_indices引用已封存F3 audit.layers.L1.evidence，symbol含原名；L2 state_vars也为原名。ENV_FLOW spellings为保留环境表达式。prepare_spelling.load_result(row)的result.mapping提供文件内原名→vN双射。后续M2必须明确sidecar依赖及匿名化，不假设边已带DEF/USE名。图store/seal和audit引用已核验。

## 5. CFG与modifier

证据：recon/cfg.py及sections.cfg。以下分母不含modifier定义，和第3节口径不同。这里只验CFG构建及映射，不能称RD收敛或完整Solidity支持率。

|任务|含体函数|legacy支持|legacy→v2支持|入口可投影|全部事件可投影|
|---|---:|---:|---:|---:|---:|
|重入合约|3404|2035|3135|3081|1947|
|重入节点|2045|1210|1964|1928|1067|
|访问控制合约|3148|2128|2797|2760|2315|
|访问控制节点|1958|1550|1859|1835|1657|

缺失投影主要为原HCG缺少emit/revert/fallback节点。语义中间块应保留，投影缺失计数；不能为了可投影而删掉控制语义。

|任务|modifier定义|调用AST|绑定成功|其中继承|失败|支持prefix执行/含调用函数|
|---|---:|---:|---:|---:|---:|---:|
|重入合约|165|609|549|266|60|285/537|
|重入节点|56|193|178|88|15|107/171|
|访问控制合约|158|613|528|283|85|261/549|
|访问控制节点|61|218|195|86|23|111/197|

绑定成功不等于复杂modifier执行受支持。调用AST可能含基类构造语法，失败不自动表示缺少权限检查。HCG CFG有next_line/first_next_line/pos_next/neg_next/end_if，两端精确归属不同函数的边分别88/1/147/67；其他未确定端点另列。建议主路线为已有语义CFG+精确投影，HCG仅作待核验拓扑备用。

条件支配汇合后的语句不代表只有条件成立才会执行；当前后继集合无分支极性，require/assert无显式异常出口。NS-P3需明确守卫语义，未知不能写成无守卫。本轮未新增支配算法或修改CFG。

## 6. 历史资源

resources.csv已对照8H reports/receipt.json SHA，170个唯一任务/折/seed/剖面恰好等于原计划。完整逐fit记录在sections.inputs.resources。

|任务|剖面|次数|平均fit秒|峰值allocated MiB|峰值reserved MiB|最低free MiB|
|---|---|---:|---:|---:|---:|---:|
|访问控制合约|G0|5|64.86|920.52|994.00|943.00|
|访问控制合约|G1R|5|73.90|1255.67|1428.00|557.00|
|访问控制合约|G2R|5|77.83|1353.42|1538.00|447.00|
|访问控制合约|G3|5|73.29|1171.28|1328.00|657.00|
|访问控制合约|G3R|5|81.59|1402.50|1594.00|377.00|
|访问控制节点|G0|10|89.42|583.47|678.00|1354.00|
|访问控制节点|G0P|10|105.70|841.61|912.00|1069.00|
|访问控制节点|G1R|10|103.62|766.74|898.00|1083.00|
|访问控制节点|G2R|10|108.44|820.24|960.00|1029.00|
|访问控制节点|G3|10|110.00|712.71|824.00|1165.00|
|访问控制节点|G3R|10|106.67|851.25|946.00|1043.00|
|重入合约|G0|5|84.47|1230.84|1410.00|400.00|
|重入合约|G1R|5|100.51|1670.70|1838.00|71.00|
|重入合约|G2R|5|92.80|1829.50|2028.00|58.00|
|重入合约|G3|5|91.59|1575.06|1804.00|93.00|
|重入合约|G3R|5|101.95|1895.21|2094.00|44.00|
|重入节点|G0|10|100.82|808.57|936.00|999.00|
|重入节点|G0P|10|118.51|1246.44|1408.00|473.00|
|重入节点|G1R|10|118.87|1106.44|1310.00|537.00|
|重入节点|G2R|10|120.22|1223.06|1370.00|517.00|
|重入节点|G3|10|114.97|1040.68|1244.00|570.00|
|重入节点|G3R|10|114.32|1259.13|1444.00|339.00|

|批次|新fit|历史训练计算参照/小时|
|---|---:|---:|
|N-A|180|4.814|
|N-B|90|2.473|
|N-C|120|3.475|
|N-D|60|1.738|

不是NodeSem总耗时承诺；未含CPU构造/验收、编码器、LLM、教师、蒸馏、新适配层和早停变化。N-B零层用原G0两层耗时占位，需NS-P4实测。最终实验按用户安排使用显存充足服务器；RTX3050 4GiB仅是本机开发限制，本轮未新测GPU或开始训练。

## 7. 获批处理与后续待确认

已获批：NS-P0用探针断言+两套已有回归，专用tests目录留到NS-P1。原plan.runtime的字面等值检查已因此前获批cache/resume修订而不成立；当前源码与runtime_resume_v2完全一致，execution.load只读通过。没有新增豁免、改旧seal。

以下仅建议，未替换方案、未改PROMPTS或冻结算法，实施前需征求用户：
1. Projector读取结构性label取得AST锚点，与未来“禁止任何label”冲突；建议明确仅身份对齐边界并做目标标签扰动不变测试。
2. M2需引用已封存L1 sidecar取得变量名，再经8G匿名化；不能把symbol内路径/绝对坐标写入特征。
3. NS-P3区分已确认守卫通过路径与普通条件支配；缺失保持未知。

这些是后续实现前的澄清；本轮A/B/C未受阻。停止于NS-P0，不自动启动NS-P1。

## 8. 实际命令、测试及限制

仓库根目录，mando：

```bash
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
python -B -m scripts.node_sem.recon.run
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
```

脚本stdout输出JSON，stderr输出进度。本次调用run()后写入新recon.json并合入独立回归/文档校验。重跑勿覆盖已有验收文件。总侦察169.64s。

DFG v2：2653通过，0失败/跳过，9警告，171.91s；原回归223通过，0失败/跳过，29警告，4.16s。合计2876项唯一测试。5脚本Python3.7语法及全部侦察断言通过。警告为既有DGL/distutils、NetworkX gpickle弃用，未升级依赖。已有回归内有合成fixture训练，不属于新增真实fit。

未实施完整NodeSemAdapter/特征/离线模型/LLM/正式计划，未开始真实训练、下载、安装或push。三份文档只追加，已有DFG文件未修改；本地提交按NS-P0前缀执行。

## 9. 完整输入引用与实际配置

以下逐项保留8H原值，合约/节点学习率分别保留；60份initial/receipt另见JSON。所有身份均取自manifest，不按文件名猜测。

### 重入合约 / reentrancy_contract

```json
{
  "graphs": {
    "G0": {
      "path": "/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/prepared/E0/contract.gpickle",
      "sha256": "7b99f680024296f557ce9d0a16ab027f7174c26c1c9d7c621390b72b1ec92452",
      "fingerprint": "6082c6b11a3d1b615856e51022b371e34864ed089f8665047568f48fbb33f149",
      "computation_fingerprint": "d21b57f60156bc2833f2fe5390ebb50ce901fa9338cda49ee4d69f2d513622ab",
      "nodes": 18312,
      "edges": 19267
    },
    "G3R": {
      "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/reentrancy_contract/F3/hcg.gpickle",
      "sha256": "eee05276a1e0ac16e54b166d0db7c2e6c8a112f3f32976fc80d85d19126970df",
      "fingerprint": "6632882d5e2d8521b2835183ba148708915139f472e6efbf56996bc49e4ba673",
      "computation_fingerprint": "0ba65d9ba9911c6b66c9a1ca4670ed39ac6275a4a966576bbd7ea612db5e8f33",
      "nodes": 18610,
      "edges": 36256
    }
  },
  "label_view": {
    "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F/label_views.json",
    "sha256": "c57bc81d501b62f8492c18f17d73352f48ad4b6d042fcf303135ce2cd214f1ef"
  },
  "labels": {
    "path": "/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/prepared/graph_labels.json",
    "sha256": "2f294a72c70680695f1bb5a5aab2a81e581795e0859a5dbf705acb36c2d650b9"
  },
  "folds": {
    "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F/folds/reentrancy_contract.json",
    "sha256": "a99558ec5a16aff1fce35c4988f2559b154c5f15446e532c74c85f7e78811f2f"
  },
  "features": {
    "original": {
      "manifest": {
        "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/features/reentrancy_contract/original_manifest.json",
        "sha256": "23350f93bb06780f285b19501621e4e5343a09c7181b535767669d78eba89357"
      },
      "npz": {
        "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/features/reentrancy_contract/original.npz",
        "sha256": "45a137ac4b772e12157b45e58afb4b2e4987da9f53f2cdb1b6c7562a241158cc"
      },
      "view": "original",
      "rows": 18312,
      "feature_shape": [
        18312,
        512
      ],
      "dtype": "float32",
      "array_min": 0.0,
      "array_max": 31888.0,
      "all_values_nonnegative_integers": true,
      "unique_original_node_ids": 18312,
      "all_row_vector_sha_verified": true,
      "auxiliary_features_unchanged": true
    },
    "anonymous": {
      "manifest": {
        "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/features/reentrancy_contract/anonymous_manifest.json",
        "sha256": "30bca5710e03777bfa383137fd066af002669757388f2f1071e7cebd90259372"
      },
      "npz": {
        "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/features/reentrancy_contract/anonymous.npz",
        "sha256": "2b2992a2034eaa93c538de64103431c719c6ab84539f88f96d31a258925296cb"
      },
      "view": "anonymous",
      "rows": 18312,
      "feature_shape": [
        18312,
        512
      ],
      "dtype": "float32",
      "array_min": 0.0,
      "array_max": 31899.0,
      "all_values_nonnegative_integers": true,
      "unique_original_node_ids": 18312,
      "all_row_vector_sha_verified": true,
      "auxiliary_features_unchanged": true
    }
  },
  "config": {
    "seed": 1,
    "schedule_epochs": 50,
    "hidden_size": 128,
    "layers": 2,
    "heads": 8,
    "use_norm": true,
    "dropout": 0.2,
    "feature": "inside_token",
    "optimizer": "Adam",
    "initial_lr": 0.0005,
    "max_lr": 0.01,
    "div_factor": 20,
    "final_div_factor": 1,
    "cycle_momentum": true,
    "weight_decay": 5e-06,
    "loss": "unweighted_cross_entropy",
    "patience": 7,
    "delta": 0.001,
    "selection": "strict minimum inner validation loss; post-update eval forward",
    "primary_checkpoint": "best",
    "secondary_checkpoint": "last",
    "batch": "inner_train node mask or file batch; one optimizer step per epoch",
    "schema_policy": "registered_schema_allow_train_unseen",
    "partition_policy": "group_disjoint_nested_file_supervision",
    "device": "cuda:0",
    "threads": 2,
    "metric_unit": "source file",
    "protocol": "dfg-v2-grouped-nested",
    "protocol_version": "dfg-v2-grouped-nested-v1",
    "forward_scope": "full_fixed_task_graph",
    "score_role": "outer_test",
    "mode": "full",
    "maximum_training_epochs": 50,
    "environment": {
      "python": "3.7.12 | packaged by conda-forge | (default, Oct 26 2021, 06:08:21) \n[GCC 9.4.0]",
      "torch": "1.8.1+cu111",
      "dgl": "0.6.1",
      "sklearn": "1.0.2",
      "numpy": "1.21.6",
      "networkx": "2.6.3"
    },
    "layer_impl": "shared_projection",
    "selection_role": "inner_val"
  }
}
```

### 重入节点 / reentrancy_node

```json
{
  "graphs": {
    "G0": {
      "path": "/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/prepared/E0/node.gpickle",
      "sha256": "91c3bd89af18af073162648b95747319b644dd2555cfcff394d251f626bbf77c",
      "fingerprint": "8aea5247b68c818ccc16a288b8c4085eccd88e1490c464b02801967a94f721a9",
      "computation_fingerprint": "dfedd0b2a300fe60b15b37932e2951b836ae892d7af02590a57bca7511d7fca3",
      "nodes": 12036,
      "edges": 11710
    },
    "G3R": {
      "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/reentrancy_node/F3/hcg.gpickle",
      "sha256": "ead61ea0bb5db8fb68675fd7d91bc91d6d6fc63c60c5fd330b9730751369ff53",
      "fingerprint": "9d738e25771643f82535933b1d1f99c4e3cf465b691765852f39f08872de7fff",
      "computation_fingerprint": "8aa7f2f6d71125195da68ddb680a116105389c1ace6c69d0140d4a977abe9e1e",
      "nodes": 12223,
      "edges": 23703
    }
  },
  "label_view": {
    "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F/label_views.json",
    "sha256": "c57bc81d501b62f8492c18f17d73352f48ad4b6d042fcf303135ce2cd214f1ef"
  },
  "labels": {
    "path": "/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/prepared/graph_labels.json",
    "sha256": "2f294a72c70680695f1bb5a5aab2a81e581795e0859a5dbf705acb36c2d650b9"
  },
  "folds": {
    "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F/folds/reentrancy_node.json",
    "sha256": "5fb23ab29bed78993422283aca3c081e9cddf3faee8c3e8005d530cf84ba88ff"
  },
  "features": {
    "original": {
      "manifest": {
        "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/features/reentrancy_node/original_manifest.json",
        "sha256": "0fb63e589115916cbed5c573b97b4b649a05fb168c0eb19b30cd6c590d3c1db8"
      },
      "npz": {
        "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/features/reentrancy_node/original.npz",
        "sha256": "96b79f29d08e35011151aa7db79419ace9b93fbc1b125f7c602ca127e453cd45"
      },
      "view": "original",
      "rows": 12036,
      "feature_shape": [
        12036,
        512
      ],
      "dtype": "float32",
      "array_min": 0.0,
      "array_max": 31888.0,
      "all_values_nonnegative_integers": true,
      "unique_original_node_ids": 12036,
      "all_row_vector_sha_verified": true,
      "auxiliary_features_unchanged": true
    },
    "anonymous": {
      "manifest": {
        "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/features/reentrancy_node/anonymous_manifest.json",
        "sha256": "d94044c90d8aa86f7a79dbab062470120fc19faf63d471cb57984430cf2d46a1"
      },
      "npz": {
        "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/features/reentrancy_node/anonymous.npz",
        "sha256": "a86daf420e979388cf56fbd277961c33508ba0c089d71a636011562018e478eb"
      },
      "view": "anonymous",
      "rows": 12036,
      "feature_shape": [
        12036,
        512
      ],
      "dtype": "float32",
      "array_min": 0.0,
      "array_max": 31899.0,
      "all_values_nonnegative_integers": true,
      "unique_original_node_ids": 12036,
      "all_row_vector_sha_verified": true,
      "auxiliary_features_unchanged": true
    }
  },
  "config": {
    "seed": 1,
    "schedule_epochs": 50,
    "hidden_size": 128,
    "layers": 2,
    "heads": 8,
    "use_norm": true,
    "dropout": 0.2,
    "feature": "inside_token",
    "optimizer": "Adam",
    "initial_lr": 0.0002,
    "max_lr": 0.005,
    "div_factor": 25,
    "final_div_factor": 1,
    "cycle_momentum": true,
    "weight_decay": 0.0,
    "loss": "unweighted_cross_entropy",
    "patience": 7,
    "delta": 0.001,
    "selection": "strict minimum inner validation loss; post-update eval forward",
    "primary_checkpoint": "best",
    "secondary_checkpoint": "last",
    "batch": "inner_train node mask or file batch; one optimizer step per epoch",
    "schema_policy": "registered_schema_allow_train_unseen",
    "partition_policy": "group_disjoint_nested_file_supervision",
    "device": "cuda:0",
    "threads": 2,
    "metric_unit": "HCG node",
    "protocol": "dfg-v2-grouped-nested",
    "protocol_version": "dfg-v2-grouped-nested-v1",
    "forward_scope": "full_fixed_task_graph",
    "score_role": "outer_test",
    "mode": "full",
    "maximum_training_epochs": 50,
    "environment": {
      "python": "3.7.12 | packaged by conda-forge | (default, Oct 26 2021, 06:08:21) \n[GCC 9.4.0]",
      "torch": "1.8.1+cu111",
      "dgl": "0.6.1",
      "sklearn": "1.0.2",
      "numpy": "1.21.6",
      "networkx": "2.6.3"
    },
    "layer_impl": "shared_projection",
    "selection_role": "inner_val"
  }
}
```

### 访问控制合约 / access_control_contract

```json
{
  "graphs": {
    "G0": {
      "path": "/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/access_control_author/prepared/E0/contract.gpickle",
      "sha256": "d66b920801c02dc53832337de719135f8c10d158b24ba403d788c1646b8f034f",
      "fingerprint": "98b022bd884c282d2fae1b072a42b1f4a4a9a5f345ae6e6c3a1856627b138e55",
      "computation_fingerprint": "63c5dc4b32386283c8d22af80a7f685096b0200cadfb64be17986b810524c61a",
      "nodes": 13432,
      "edges": 15538
    },
    "G3R": {
      "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/access_control_contract/F3/hcg.gpickle",
      "sha256": "9c0140328b8a12a0822405bb9c04108dac2596f9baa6e99764ace8b5479b9df3",
      "fingerprint": "93b265e38d36413f9637aa1e77afc511a6a82432377003ce4c5c48d787ac3539",
      "computation_fingerprint": "1da207d5c9f28876202a9b6243998c9c9ac84b14c34647d45d1fda6fc7ab3a01",
      "nodes": 13693,
      "edges": 27664
    }
  },
  "label_view": {
    "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F/label_views.json",
    "sha256": "c57bc81d501b62f8492c18f17d73352f48ad4b6d042fcf303135ce2cd214f1ef"
  },
  "labels": {
    "path": "/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/access_control_author/prepared/graph_labels.json",
    "sha256": "6002778325eca7b981f3a1f996a31c34ccfa1d83b5166d3c28ee37c974384649"
  },
  "folds": {
    "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F/folds/access_control_contract.json",
    "sha256": "fa5fe375b74b9bdd373c23b240e290a89be0168f1c5839117848293e304c0710"
  },
  "features": {
    "original": {
      "manifest": {
        "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/features/access_control_contract/original_manifest.json",
        "sha256": "e77efd1fff200054642aa52a3fa0d26499a1f4f7ebf3d15ae018c815c5a58edd"
      },
      "npz": {
        "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/features/access_control_contract/original.npz",
        "sha256": "872ab0f016590cb7c9f7281ec1ccc1650f45b543cd971a6251427b454239acf6"
      },
      "view": "original",
      "rows": 13432,
      "feature_shape": [
        13432,
        512
      ],
      "dtype": "float32",
      "array_min": 0.0,
      "array_max": 31973.0,
      "all_values_nonnegative_integers": true,
      "unique_original_node_ids": 13432,
      "all_row_vector_sha_verified": true,
      "auxiliary_features_unchanged": true
    },
    "anonymous": {
      "manifest": {
        "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/features/access_control_contract/anonymous_manifest.json",
        "sha256": "5c7d5e3a46b4f8a4aa5eb49083c0881c67537decdcb79e711a05a9bee48d0320"
      },
      "npz": {
        "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/features/access_control_contract/anonymous.npz",
        "sha256": "f196081282f4ce54b77e23bac8f73fb71f8a3a9adf3ac89f98bd44f2cf0aac8e"
      },
      "view": "anonymous",
      "rows": 13432,
      "feature_shape": [
        13432,
        512
      ],
      "dtype": "float32",
      "array_min": 0.0,
      "array_max": 31922.0,
      "all_values_nonnegative_integers": true,
      "unique_original_node_ids": 13432,
      "all_row_vector_sha_verified": true,
      "auxiliary_features_unchanged": true
    }
  },
  "config": {
    "seed": 1,
    "schedule_epochs": 50,
    "hidden_size": 128,
    "layers": 2,
    "heads": 8,
    "use_norm": true,
    "dropout": 0.2,
    "feature": "inside_token",
    "optimizer": "Adam",
    "initial_lr": 0.0005,
    "max_lr": 0.01,
    "div_factor": 20,
    "final_div_factor": 1,
    "cycle_momentum": true,
    "weight_decay": 5e-06,
    "loss": "unweighted_cross_entropy",
    "patience": 7,
    "delta": 0.001,
    "selection": "strict minimum inner validation loss; post-update eval forward",
    "primary_checkpoint": "best",
    "secondary_checkpoint": "last",
    "batch": "inner_train node mask or file batch; one optimizer step per epoch",
    "schema_policy": "registered_schema_allow_train_unseen",
    "partition_policy": "group_disjoint_nested_file_supervision",
    "device": "cuda:0",
    "threads": 2,
    "metric_unit": "source file",
    "protocol": "dfg-v2-grouped-nested",
    "protocol_version": "dfg-v2-grouped-nested-v1",
    "forward_scope": "full_fixed_task_graph",
    "score_role": "outer_test",
    "mode": "full",
    "maximum_training_epochs": 50,
    "environment": {
      "python": "3.7.12 | packaged by conda-forge | (default, Oct 26 2021, 06:08:21) \n[GCC 9.4.0]",
      "torch": "1.8.1+cu111",
      "dgl": "0.6.1",
      "sklearn": "1.0.2",
      "numpy": "1.21.6",
      "networkx": "2.6.3"
    },
    "layer_impl": "shared_projection",
    "selection_role": "inner_val"
  }
}
```

### 访问控制节点 / access_control_node

```json
{
  "graphs": {
    "G0": {
      "path": "/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/access_control_author/prepared/E0/node.gpickle",
      "sha256": "c3bdfa00bd112581fd4900ac59ab192ad32a9a26df94dc87209e1ba900208488",
      "fingerprint": "f36690386429bd953135c06cc91d2ed3f59010a6d044935e20f063914bc2971f",
      "computation_fingerprint": "30d299e9492d5b50d1ea7b2136658d700d23b1ed487e293c502a17936eb402a1",
      "nodes": 7710,
      "edges": 8840
    },
    "G3R": {
      "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/access_control_node/F3/hcg.gpickle",
      "sha256": "ed86b79ab971fdad32fabe249ddb0902591d07ba217b90c9ae3082b7f430028c",
      "fingerprint": "4e45cef75550d9f449d10d7f411eb9c0395db53139c7bb4cebddebed54f6b8eb",
      "computation_fingerprint": "43136752ce1374ef4a5feda74fffcc8ef46f1567c4ebf4308dbb09a03bb4a6aa",
      "nodes": 7892,
      "edges": 16569
    }
  },
  "label_view": {
    "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F/label_views.json",
    "sha256": "c57bc81d501b62f8492c18f17d73352f48ad4b6d042fcf303135ce2cd214f1ef"
  },
  "labels": {
    "path": "/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/access_control_author/prepared/graph_labels.json",
    "sha256": "6002778325eca7b981f3a1f996a31c34ccfa1d83b5166d3c28ee37c974384649"
  },
  "folds": {
    "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F/folds/access_control_node.json",
    "sha256": "614497ddee0192d0319b29ab2810de4b48a4b0bc9c92a40a21a33dae98668a82"
  },
  "features": {
    "original": {
      "manifest": {
        "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/features/access_control_node/original_manifest.json",
        "sha256": "7c08c8ad4d437140ba377ec0e588dc56aa210b6708edf07341274dab71ccce02"
      },
      "npz": {
        "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/features/access_control_node/original.npz",
        "sha256": "f9aa1bac2fb99d3dc9fd8a99b774053e40e22735e3d8161faa29fd6ee4d7feac"
      },
      "view": "original",
      "rows": 7710,
      "feature_shape": [
        7710,
        512
      ],
      "dtype": "float32",
      "array_min": 0.0,
      "array_max": 31888.0,
      "all_values_nonnegative_integers": true,
      "unique_original_node_ids": 7710,
      "all_row_vector_sha_verified": true,
      "auxiliary_features_unchanged": true
    },
    "anonymous": {
      "manifest": {
        "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/features/access_control_node/anonymous_manifest.json",
        "sha256": "a3b0fd9a0b605c74461a6d0761b457ac291da7591a315914a4f55ba2fae92f3f"
      },
      "npz": {
        "path": "/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/features/access_control_node/anonymous.npz",
        "sha256": "cb3f430a0ed2ea3be353655603b0f55bd80e9eb9014e23a13b953cc524b9f8f7"
      },
      "view": "anonymous",
      "rows": 7710,
      "feature_shape": [
        7710,
        512
      ],
      "dtype": "float32",
      "array_min": 0.0,
      "array_max": 31899.0,
      "all_values_nonnegative_integers": true,
      "unique_original_node_ids": 7710,
      "all_row_vector_sha_verified": true,
      "auxiliary_features_unchanged": true
    }
  },
  "config": {
    "seed": 1,
    "schedule_epochs": 50,
    "hidden_size": 128,
    "layers": 2,
    "heads": 8,
    "use_norm": true,
    "dropout": 0.2,
    "feature": "inside_token",
    "optimizer": "Adam",
    "initial_lr": 0.0002,
    "max_lr": 0.005,
    "div_factor": 25,
    "final_div_factor": 1,
    "cycle_momentum": true,
    "weight_decay": 0.0,
    "loss": "unweighted_cross_entropy",
    "patience": 7,
    "delta": 0.001,
    "selection": "strict minimum inner validation loss; post-update eval forward",
    "primary_checkpoint": "best",
    "secondary_checkpoint": "last",
    "batch": "inner_train node mask or file batch; one optimizer step per epoch",
    "schema_policy": "registered_schema_allow_train_unseen",
    "partition_policy": "group_disjoint_nested_file_supervision",
    "device": "cuda:0",
    "threads": 2,
    "metric_unit": "HCG node",
    "protocol": "dfg-v2-grouped-nested",
    "protocol_version": "dfg-v2-grouped-nested-v1",
    "forward_scope": "full_fixed_task_graph",
    "score_role": "outer_test",
    "mode": "full",
    "maximum_training_epochs": 50,
    "environment": {
      "python": "3.7.12 | packaged by conda-forge | (default, Oct 26 2021, 06:08:21) \n[GCC 9.4.0]",
      "torch": "1.8.1+cu111",
      "dgl": "0.6.1",
      "sklearn": "1.0.2",
      "numpy": "1.21.6",
      "networkx": "2.6.3"
    },
    "layer_impl": "shared_projection",
    "selection_role": "inner_val"
  }
}
```
