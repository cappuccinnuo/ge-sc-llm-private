"""Render Prompt 0 evidence; no graph analysis or training is implemented here."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(headers, rows):
    def cell(value):
        return str(value).replace('|', r'\|').replace('\n', '<br>')
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(cell(x) for x in row) + ' |' for row in rows])


def write_new(path, content):
    with path.open('x', encoding='utf-8') as handle:
        handle.write(content)


def run(evidence):
    evidence = Path(evidence).resolve()
    for name in ('RECON.md', 'recon.json', 'PROGRESS.md'):
        if (HERE / name).exists():
            raise FileExistsError(str(HERE / name))
    before = read(evidence / 'before.json')
    graphs = read(evidence / 'graphs/summary.json')
    tokens = read(evidence / 'token/summary.json')
    protocol = read(evidence / 'protocol/protocol_resources.json')
    scalar = read(evidence / 'scalar/summary.json')
    protection = read(evidence / 'protection.json')
    tasks = graphs['tasks']
    task_ids = [t['task_id'] for t in tasks]
    for data in (tokens, protocol, scalar):
        assert [t['task_id'] for t in data['tasks']] == task_ids
    accepted = {t['task_id']: (not t['missing_sources'] and not t['parse_errors'] and
                t['source_paths_unique'] and
                t['supported_view']['anchor_fraction_all_parsed_declarations'] >= .9)
                for t in tasks}
    assert all(accepted.values()) and tokens['all_samples_exact']
    assert not protection['changed'] and protection['prompt_unchanged']
    approval = {
        'approved_by': 'user', 'response': '同意复用已有 SupportedSourceView（推荐）',
        'scope': 'DFG v2 source view policy and Prompt 0 anchor acceptance only',
        'class': 'scripts.DFG.state.stage_k.profile.SupportedSourceView',
        'use_existing_recorded_metadata': True, 'unverified_version_fallback_preserved': True,
        'new_state_nodes': False, 'old_scalar_baseline_unchanged': True,
        'original_policy': 'scripts.DFG.frontend.SourceView',
        'original_all_gates_passed': graphs['all_anchor_gates_passed'],
        'accepted_gates': accepted,
    }
    files = ['before.json', 'protection.json', 'regression.log', 'graphs/summary.json',
             'graphs/legacy_var_ast.json', 'token/summary.json', 'token/selection.json',
             'token/execution_receipt.json', 'protocol/protocol_resources.json',
             'protocol/fit_records.json', 'protocol/resource_summary.csv', 'scalar/summary.json']
    for task_id in task_ids:
        files += ['graphs/' + task_id + '.json', 'scalar/' + task_id + '/audit.json',
                  'scalar/' + task_id + '/inputs.json', 'scalar/' + task_id + '/manifest.json']
    refs = [{'path': str(evidence / f), 'sha256': sha(evidence / f)} for f in files]
    reasons = []
    for t in tasks:
        detail = read(evidence / 'graphs' / (t['task_id'] + '.json'))
        for f in detail['files']:
            if f['views']['supported_view']['status'] != 'verified':
                first = f['declarations'][:1]
                reasons.append({'task_id': t['task_id'], 'file': f['file'],
                    'reason': f['views']['supported_view']['reason'],
                    'declarations': len(f['declarations']), 'example': first})
    result = {
        'version': 'dfg-v2-prompt0-recon-v1', 'created_utc': datetime.now(timezone.utc).isoformat(),
        'base_head': before['head'], 'branch': before['branch'], 'prompt_sha256': before['prompt_sha256'],
        'status': 'passed_with_user_approved_source_view', 'scope': 'Prompt 0 only',
        'source_view_decision': approval, 'graphs': graphs, 'unverified_anchor_examples': reasons,
        'tokens': tokens, 'training_protocol_and_history': protocol, 'scalar_baseline': scalar,
        'protection': protection, 'evidence': refs,
        'tests': {'command': 'python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py',
                  'passed': 223, 'failed': 0, 'warnings': 29, 'seconds': 4.03,
                  'new_algorithm_tests': 'not applicable: Prompt 0 adds audit probes only'},
        'remote_refresh': before['remote_refresh'], 'training_executed': False,
        'new_dfg_algorithm_implemented': False,
        'pending_design_decisions': [
            'Do not select G* using outer-test F1 while claiming independent test evaluation; ask user before changing plan.',
            'v2 nested checkpoint binding requires an explicit adapter; paper_checkpoint is hard-coded to paper protocol.',
        ],
    }
    sections = ['# DFG v2 Prompt 0：侦察与基线核对',
        '**结论：经用户批准复用已有 `SupportedSourceView` 后，Prompt 0 数据验收通过。** '
        '原 `SourceView` 下访问控制合约任务的状态声明锚点率为 804/922（87.20%），曾低于90%门槛并暂停。'
        '用户明确答复“同意复用已有 SupportedSourceView（推荐）”；批准口径为872/922（94.58%）。'
        '这里保留两个口径及失败证据，不把原失败记录改成通过。未新增状态节点，未猜测编译器版本。',
        '工作树：`' + str(ROOT) + '`；分支 `dfg-v2`；审计基础提交 `' + before['head'] + '`。'
        '该分支在开始时已经存在。`git fetch origin dfg-v2` 因 GitHub DNS 解析失败，未能确认远端最新状态；'
        '本地 HEAD 与缓存 origin/dfg-v2 一致，并包含文档指定的 ddg-v1.1-correctness 基线。未推送。',
        '证据目录记为 **B**：`' + str(evidence) + '`。机器汇总见同目录代码侧的 `recon.json`，'
        '逐文件审计在 `B/graphs/<task>.json`；报告中 R=重入，AC=访问控制。',
        '## 1. 输入图、源码与 schema',
        '入口为 `integration/rebuild.py::DEFAULT_MANIFEST`，引用的 manifest 及每个输入 SHA 已核对。'
        '**本批输入是作者发布的图结构/节点标签，加上本地已冻结的 tokenizer 特征。** '
        '节点任务使用漏洞文件的 HCG（CFG+CG）子集，不能把它与作者另发的 CFG-only 图混称为同一输入。',
        table(['任务', '文件', '节点', '边', '节点类型', '边类型', '原始 canonical 类型'],
              [[t['task_id'], t['files'], t['nodes'], t['edges'], len(t['node_types']),
                len(t['edge_types']), len(t['canonical_counts'])] for t in tasks]),
        '合约任务的文件/节点/边数量与仓库 `audit_author_graphs.py::PAPER` 所记录的论文表1一致：'
        'R=142/18312/19267，AC=114/13432/15538。节点任务文件数分别71、57，是上述语料的漏洞文件子集；'
        '不拿节点子集数量直接比较表1的完整语料数量，也不据此宣称标签语义已完全复现论文。',
        '四任务均无缺失源码，source_file → 唯一路径与源码 SHA 均已核验，节点 ID 全为整数。'
        '全部原节点属性键：`' + '`, `'.join(tasks[0]['node_attribute_keys']) + '`。'
        '原始 canonical 计数指 NetworkX 图中的 (源类型, 边类型, 目标类型)，不是 reflect 后的模型 schema。',
    ]
    for t in tasks:
        sections += ['### ' + t['task_id'],
            '- 图：`' + t['graph']['path'] + '`\n- SHA256：`' + t['graph']['sha256'] + '`\n'
            '- 源码清单：`' + t['source_manifest']['path'] + '`',
            '节点类型计数：`' + json.dumps(t['node_types'], ensure_ascii=False) + '`。\n\n'
            '边类型计数：`' + json.dumps(t['edge_types'], ensure_ascii=False) + '`。\n\n'
            '每个 canonical 的边数完整保存在 `recon.json → graphs.tasks[].canonical_counts`。']
    sections += ['## 2. 状态声明锚点与源码版本策略',
        table(['任务', '声明总数', '原 SourceView', '批准 SupportedSourceView', '验证文件', 'ordinary_nodes_checked'],
              [[t['task_id'], t['supported_view']['declarations'],
                '%d (%.2f%%)' % (t['source_view']['new_variable_anchors'], 100*t['source_view']['anchor_fraction_all_parsed_declarations']),
                '%d (%.2f%%)' % (t['supported_view']['new_variable_anchors'], 100*t['supported_view']['anchor_fraction_all_parsed_declarations']),
                '%d/%d' % (t['supported_view']['verified_files'], t['files']),
                t['supported_view']['ordinary_nodes_checked']] for t in tasks]),
        '锚点链为原源码 AST 字节身份 → view.mapping → compat_ids → Projector.by_ast；'
        '所有已验证声明的目标类型都是 `new_variable`。未验证项保留在分母中；'
        '四任务无解析失败，已验证文件中没有“状态声明确无对应节点”的案例。'
        '合约任务残余 R=9、AC=50 个声明属于版本/视图无法确认，不能把它们写成“原图丢失声明节点”。',
        '原视图原因及计数、批准视图原因及计数均保留在 `recon.json`。批准口径的文件级回退如下：',
        table(['任务', '文件', '原因', '声明数', '示例原始行'],
              [[x['task_id'], x['file'], x['reason'], x['declarations'],
                x['example'][0]['line'] if x['example'] else '无状态声明'] for x in reasons]),
        '对应声明全文、字节范围、原始行号在 `recon.json → unverified_anchor_examples` 和逐文件 JSON 中。'
        '多 pragma 的恢复复用 Stage K 的版本区间处理与已有 source SHA 绑定元数据；'
        '不把 pragma 范围伪装成一个确定的 solc 版本。未确认部分保留回退。'
        '批准只涉及 v2 的后续视图策略，本次旧标量对照依旧使用未修改的原 pipeline。',
        '## 3. 语句节点覆盖与 legacy AST',
        '以下为批准视图口径，每格依次是 **精确匹配 / 无独立精确节点 / 视图未确认**。'
        '分类直接来自当前 grammar AST；modifier/constructor 行是上面语句集合的上下文子集，不能重复相加。',
    ]
    kinds = sorted(set(k for t in tasks for k in t['supported_view']['statement_coverage']) |
                   {'do_while_statement', 'throw_statement'})
    rows = []
    for kind in kinds:
        row = [kind]
        for t in tasks:
            counts = t['supported_view']['statement_coverage'].get(kind, {})
            row.append('/'.join(str(counts.get(k, 0)) for k in ('matched','no_exact_hcg_node','view_unverified')))
        rows.append(row)
    sections += [table(['AST/上下文', 'R 合约', 'AC 合约', 'R 节点', 'AC 节点'], rows),
        '`emit_statement` 与 `revert_statement` 在已验证文件中均无独立 HCG 锚点。'
        '`do_while_statement`、`throw_statement` 是本次 AST 类型枚举未观察到的类型，'
        '不等同于断言原始文本没有其他语法表示。构造器上下文仅统计 grammar 的 `constructor_definition`，'
        '没有把老式同合约名 function 自动推断为构造器。'
        'for-update 单列的是 update AST 自身是否有独立精确节点；不按最近行猜映射。'
        '缺独立语句节点不直接等于整个语句的所有子事实都无法映射，后续应按事实精确投影计数。',
        'legacy 示例（仅解析器验证，未进行 Solidity 编译验证）：',
        '```text\nvariable_declaration_statement: var acc = Acc[msg.sender];\n'
        '  [无字段] variable_declaration\n    type: type_name -> primitive_type -> var\n'
        '    name: identifier acc\n  [无字段] =\n  value: array_access\n'
        '    base: identifier Acc\n    index: member_expression\n'
        '      object: identifier msg\n      property: identifier sender\n```',
        '完整含标点、子节点与字段的 AST：`B/graphs/legacy_var_ast.json`。',
        '## 4. tokenizer 特征核对',
        'tokenizer：`Salesforce/codet5p-770m`，revision '
        '`3f7cc6e80aee6612f41253b5ee28f09f86faa35f`，`RobertaTokenizerFast`，离线缓存加载。'
        '输入为节点 `code` 原样文本，保留已有 DOT 引号/转义，不额外规范化。'
        '先 `add_special_tokens=True` 编码，再由现有 `encode_ids` 取前512个 ID、右侧补0、转为 `float32[512]`。'
        'pad/bos/eos/unk=0/1/2/3。没有加载 encoder 权重。',
        table(['任务','抽样节点','逐元素完全相同','抽样中发生截断'],
              [[t['task_id'],t['sampled_nodes'],t['exact_matches'],t['sample_truncated_nodes']] for t in tokens['tasks']]),
        '独立对每个任务按 seed=0 抽200节点，800/800完全一致；全图特征 shape/dtype 也已枚举。'
        '这不是全图每个向量重新编码证明，抽样和向量已封存于 `B/token/`。'
        '输入原始作者融合图没有 token；它是此前本地补入的固定特征，不应写成作者发布的语义向量。'
        '一次839-token长文本警告发生在手动截断前；最终512维一致。'
        '不能直接改用 tokenizer 的 truncation=True 并假定长文本 EOS 行为相同。',
        '## 5. 训练协议与冻结划分',
        '此处记录现有数值事实，不执行训练，也没有把历史 paper_kfold 结果改称独立测试。'
        'v2 文档拟用嵌套验证；冻结外层与内层名单已经存在，不需要重抽折。',
        table(['任务','Adam initial LR','OneCycle max LR','div_factor','weight_decay','折数','fold0 train/inner val/outer test'],
              [[t['task_id'],t['config']['initial_lr'],t['config']['max_lr'],t['config']['div_factor'],
                t['config']['weight_decay'],t['k_folds'],
                '/'.join(str(t['fold_file_counts'][0][k]) for k in ('inner_train_files','inner_val_files','outer_test_files'))]
               for t in protocol['tasks']]),
        '共享配置：Adam 默认 betas=(0.9,0.999)、eps=1e-8、amsgrad=False；'
        'OneCycle cosine，50个 scheduler step，final_div_factor=1、cycle_momentum=True、'
        'base/max momentum=0.85/0.95，创建 scheduler 后 beta1=0.95，阶段结束 step=14/49。'
        '每轮一次完整 train 监督的 optimizer step，再 scheduler step，再 eval 前向验证。'
        '最多50轮，patience=7，delta=0.001；best 严格取最低验证 loss，'
        '不是最低 loss 至少差0.001才保存。delta 参与停止计数，best/last 分开。'
        '损失为不加类别权重的 cross entropy。HGT hidden=128，layers=2，heads=8，dropout=0.2。',
        '划分文件为 JSON，paper 折键 `train_files/val_files`，保留的 nested 折键 '
        '`inner_train_files/inner_val_files/outer_test_files`。四任务原 nested 文件均存在；'
        '用现有 make_fold_document 在内存重建，4/4与冻结文件内容一致，没有改写折文件。'
        'graph_labels.json 是 contract_name/targets 记录列表，节点监督标签在冻结图节点属性中。',
    ]
    for t in protocol['tasks']:
        sections += ['- `' + t['task_id'] + '`：\n'
            '  - paper：`' + t['paper_splits']['path'] + '`\n'
            '  - nested：`' + t['original_nested_splits']['path'] + '`\n'
            '  - 合约标签：`' + t['labels_file']['path'] + '`']
    sections += ['种子：split=1；inner=seed×1009+fold+1；constructor=10000+fold'
        '（合约另加1000）；pair=constructor+77；fit=constructor+1000000。'
        '所有路径、SHA、每折名单数量、实际配置见 `B/protocol/protocol_resources.json`。'
        '历史90份 fit 记录的 config 与任务 manifest 核对一致。',
        '## 6. 未修改原标量层的覆盖基线',
        '实际调用 `integration.pipeline.build_graph(profile="scalar")`，仅将结果写入新目录。'
        '没有用批准的新视图悄悄替换原标量对照。函数总数按原始 AST 中带函数体的 FUNCTION_TYPES 统计；'
        '文件级回退的函数也在总数中，避免只报告分析成功文件导致分母变小。',
        table(['任务','总函数','可进入旧文件分析','支持函数','支持/全部','文件门槛排除','新增 DATA_DEF_USE'],
              [[t['task_id'],t['raw_functions_with_body'],t['functions_in_analyzable_files'],t['functions_supported'],
                '%.2f%%' % (100*t['functions_supported']/t['raw_functions_with_body']),
                t['functions_excluded_by_file_gate'],t['DATA_DEF_USE']] for t in scalar['tasks']]),
    ]
    for t in scalar['tasks']:
        sections += ['### ' + t['task_id'] + ' 回退 Top 10',
                     table(['函数回退原因（原字符串）','次数'],t['function_fallback_top10']),
                     '文件级回退：`' + json.dumps(t['file_fallback_reasons'], ensure_ascii=False) + '`。']
    sections += ['每个新 bundle 的 `audit.json` 含原节点、属性、基础边不变量核验；'
        '图/输入/审计 SHA 在 `B/scalar/<task>/manifest.json`，单独输出新 `hcg.gpickle`。'
        '四份图均保留全部原节点与边。函数支持不保证每个事实都有可投影节点，也不等于预测质量。',
        '## 7. 历史耗时与显存',
        '统计 overall_cv_v1 实际60次 fit 与 guard_extension_v1 实际30次新 fit；不把引用的历史结果重复计数。',
        table(['批次/变体','任务','fit数','耗时中位数(s)','最大 allocated(MiB)','最大 reserved(MiB)','最低整卡空闲(MiB)'],
              [[batch['batch']+'/'+row['variant'],row['task_id'],row['fits'],'%.2f'%row['median_seconds'],
                '%.2f'%row['maximum_peak_allocated_mib'],'%.2f'%row['maximum_peak_reserved_mib'],row['minimum_card_free_mib']]
               for batch in protocol['resource_batches'] for row in batch['by_task_variant']]),
        'guard 新30次总计82.66分钟，平均165.32秒；overall 60次总计157.77分钟。'
        '这些是历史运行记录，包含各折不同早停轮数及设备状态，不是 v2/G3 的显存保证。'
        '原“150次约7小时”可作为粗估，需 Prompt 7 的实测再更新。'
        '证据：`B/protocol/fit_records.json`、`resource_summary.csv`。',
        '## 以后扩展：其余五类仅记录路径',
    ]
    for other in graphs['other_categories_paths_only']:
        sections.append('- `' + other['category'] + '`：\n' + '\n'.join(
            '  - '+key+'：`'+next(p['path'] for p in other[key] if p['exists'])+'`'
            for key in ('author_hcg','author_cfg','sources')))
    sections += ['以上仅确认路径存在；本轮未加载、核验或分析其余五类图。',
        '## 验收、范围与待用户确认的建议',
        '1. 批准口径四任务锚点均≥90%；token抽样800/800一致；原标量四任务均完成；输入SHA未变。\n'
        '2. 回归命令：`python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py`；'
        '**223 passed，0 failed，29 warnings，4.03s**。警告为现有 DGL distutils 与 NetworkX gpickle 弃用提示。\n'
        '3. 未新增分析算法，因此本阶段没有新增 DFG 语义单元测试；审计脚本用现有 Python3.7 运行，'
        '已有输出目录拒绝覆盖。编译验证、训练、v2模型构造均未执行，它们不属于本阶段。\n'
        '4. 11063个受保护的已跟踪文件 SHA 未变，PROMPTS.md 未变；原有15个未跟踪路径保留。'
        '新源码/文档只在 dfg_v2 下；另有 Prompt 0 明确要求的新产物目录 B。'
        '因此 git status 中还会出现原有未跟踪路径与该产物目录，不能为了满足“只显示v2新文件”而清理它们。\n'
        '5. 本轮优先遵循 Prompt 0 的“不修改任何已有文件”，没有向旧 HANDOVER/training_changes 追加，'
        '记录集中在新 PROGRESS.md；这与共享上下文的每轮追加要求有冲突，明确保留此处理记录。',
        '**以下建议尚未实施，进入相应阶段前需要用户确认：**\n\n'
        '- 文档按四任务 outer-test F1 选 G*，会让外层测试参与方案选择。建议改成内层选择，'
        '或固定报告全部剖面并把 G* 排名仅作探索性观察；不能继续称选出的 G* 分数是未参与选择的独立测试。\n'
        '- P7 不能直接复用 paper_checkpoint 的协议绑定：它写死 paper_kfold/CV validation。'
        '建议在 v2 旁路适配 checkpoint 的协议、评分角色、辅助节点/schema 绑定，保留训练数值规则；'
        '原保存器不修改。无训练支持关系的非零梯度断言也应按训练支持量解释。',
        '本次唯一已获批准的方案调整是 SupportedSourceView。下一阶段是 Prompt 1；本轮到此停止。',
        '## 复跑命令（每次换一个全新的输出目录）',
        '```bash\nconda activate mando\ncd '+str(ROOT)+'\n'
        'export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64\n'
        'export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2\n'
        'python -B -m scripts.DFG.dfg_v2.recon_graphs --output /tmp/dfg-v2-p0-new/graphs\n'
        'HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -B -m scripts.DFG.dfg_v2.recon_tokens --output /tmp/dfg-v2-p0-new/token --sample-size 200 --seed 0\n'
        'python -B -m scripts.DFG.dfg_v2.recon_protocol --output /tmp/dfg-v2-p0-new/protocol\n'
        'python -B -m scripts.DFG.dfg_v2.recon_scalar --output /tmp/dfg-v2-p0-new/scalar\n'
        'python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py\n```',
    ]
    progress = '''# DFG v2 实施记录

## 2026-10-23 · Prompt 0 · Codex

范围：仅侦察、输入核验与原标量层基线复跑。未开始 Prompt 1，未实现新 DFG 算法，未训练模型。

### 新文件

- `recon_graphs.py`：源码身份、AST精确投影、图/schema计数与原/支持视图分别核验。
- `recon_tokens.py`：离线冻结抽样、800个token向量重新编码逐元素比较与来源核验。
- `recon_protocol.py`：实际配置、冻结内外层划分、历史90次fit的资源记录核验。
- `recon_scalar.py`：调用未修改的旧scalar profile，保留文件级失败分母及回退原因。
- `recon_report.py`：将已有证据渲染为报告，拒绝覆盖已有报告，不包含分析算法。
- `RECON.md`、`recon.json`：人可读与机器可读验收结果。
- `PROGRESS.md`：本记录。完整审计与新基线图位于 `scripts/DFG/experiments/artifacts/dfg_v2/recon/`。

### 批准的调整

原 SourceView 的AC合约锚点仅804/922=87.20%，已按门槛暂停并询问。用户批准复用已有 SupportedSourceView 及绑定的版本元数据；批准后872/922=94.58%。R合约2360/2369=99.62%，R节点1788/1788、AC节点403/403。未知版本仍回退，不新增状态节点。原视图失败证据保留；旧 scalar 对照不采用这个变更。

### 验收结果

- token：每任务200个，800/800逐元素一致；实际是本地补入的CodeT5p-770m tokenizer ID，float32[512]，没有加载encoder。
- 原scalar四任务新增边3561/4032/1894/2836，支持函数2035/3404、2128/3148、1210/2045、1550/1958。
- 回归：`python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py`，223 passed，29个现有弃用警告，0 failed。
- 4/4原nested划分可由现有算法在内存精确重现；没有改写冻结名单。
- 11063个受保护的已跟踪文件SHA保持一致，PROMPTS.md不变；旧15个未跟踪路径保留。新产物是文档明确指定路径，未清理旧工作区。

### 处理与限制

- 当前分支已是dfg-v2，无需重新checkout。fetch因DNS失败，不能声称核验了远端最新；不push、不reset、不迁移。
- Prompt 0要求“不修改任何已有文件”与共享上下文要求追加旧HANDOVER/training_changes冲突。本轮按具体Prompt0限制只写新记录；旧文档未改。
- 未做solc编译、模型训练或v2模型构造；不把解析通过写成编译通过。
- 不保证缺失emit/revert投影能恢复；不对作者标签的语义正确性作新结论。
- 后续协议建议（G*使用outer-test选型、nested checkpoint适配）详见RECON；尚未实施，先征求用户。

### 下一步

Prompt 0数据与回归验收通过，下一步是Prompt 1骨架及模型输入；本轮停止，不自动展开后续阶段。
'''
    write_new(HERE / 'recon.json', json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    write_new(HERE / 'RECON.md', '\n\n'.join(sections) + '\n')
    write_new(HERE / 'PROGRESS.md', progress)
    print('Prompt 0 reports written; all approved gates pass')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True)
    run(parser.parse_args().evidence)