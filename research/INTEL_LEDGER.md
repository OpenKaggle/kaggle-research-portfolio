# 调研 A 组情报账本

更新时间：2026-09-11 06:55 CST  
访问时区：Asia/Shanghai  
状态：首轮本地复盘 + 首轮公开外部检索

## 记录规则

- `F`：可直接核验的事实。
- `I`：基于事实形成、尚待实验验证的推断。
- `N`：否定结果或被证伪假设。
- 外部条目记录来源 URL、发布日期（若来源明确提供）和访问日期；没有发布日期时写“未标”，不猜测。
- 社区帖子只作为候选假设，不能替代官方规则、公开代码复现或封存实验。
- 账本追加更新；纠错新增条目，不覆盖旧判断。

历史证据总索引：`reports/internal_kaggle_playbook_2026-09-09.md`。该人工验读报告明确确认四个历史目录均无 `.git`，旧 ENVDA/CRAW/ONNX 聊天正文当前不可读；因此下列历史条目不声称 commit 或对话证据。

## 本地历史证据

### L-ROGII-001 — 隐藏格式必须动态适配（F）

- 项目：ROGII Well Log。
- 证据：`reports/agent_submission_risk_2026-06-06.md`、`reports/rogii_blend_experiments_2026-06-07.md`、`reports/rogii_submission_queue.md`。
- 事实：动态读取隐藏样例的 AeroRidge v34 得分 9.150；静态可见样本写法隐藏格式失败。若干宽混合/公开来源分支显著恶化。
- 可迁移：Traffic/ARC 先运行时读取官方 schema；提交槽只回答预注册问题。

### L-NEMO-001 — 宽泛训练破坏稳定多数（N）

- 项目：NVIDIA Nemotron。
- 证据：`$HOME/Desktop/kagglenvda/handoff_package_2026-06-15/docs/FINAL_DAY_SUMMARY.md` 与 `SCORE_AND_EXPERIMENT_TIMELINE.md`。
- 事实：0.86 稳定锚点；广谱 SFT 为 0.50，config-only 与完整 key 重写为 0.51；只恢复 5,888 个 MoE expert 张量回到 0.84，全 MoE 恢复到 0.85；小型 `in_proj` 增量保持 0.86。
- 可迁移：只在明确困难尾部触发修复，默认返回锚点。

### L-CRAWL-001 — 单锚点与 replay 索引都能制造伪结论（N）

- 项目：Maze Crawler。
- 证据：`$HOME/Desktop/kagglecraw/docs/HANDOFF_20260603.md`、`reports/probe_phase_route_summary_20260606.md`、`reports/v43_v45_summary.md`。
- 事实：大量窄补丁未过门；同一 v51 公开分数从 1184.5 变为 940.8，80 局噪声可达 abs(z)=1.15；同一候选对不同锚点结论相反；正确动作位于 `steps[t+1]`，此前 off-by-one 使一批 replay 推断失效。
- 可迁移：Kaggriculture 使用同种子、多对手、双座位；所有 replay 先校验时间索引。

### L-ONNX-001 — 小 swap 可复利，大批替换会隐藏崩塌（F/N）

- 项目：NeuroGolf ONNX。
- 证据：`$HOME/Desktop/kaggleonnx/reports/HANDOFF_NEXT_AGENT.md`、`anchor_integration_ledger.md`、`solver_ledger.md`。
- 事实：本地/LB 从 6255.96 到 6260.89 逐次近乎精确匹配，证明 sealed semantic/cost harness 可信；但距当时 top-10 仍约 1,079 分且局部 sweep 无候选，方法族已触顶。另有最小 swap 本地 6246.1694、LB 6246.16，而更大 visible-clean 批次本地 6276.21、LB 5966.68。DSL 加深没有新增命中，瓶颈是原语覆盖；一个“可见失败且更便宜所以安全”的推断后来被反例推翻。
- 可迁移：ARC 单规则消融；所有安全推断可撤销；优先扩覆盖，不盲目加深。

## 当前项目内部事实

### C-KAGG-001 — hybrid 的首批远程信号（F/I）

- 本地来源：`kaggriculture/reports/progress_2026-09-09.md` 与实验账本。
- 事实：公开锚点 72 局 rating 2268.3、P10 -3676.6、最坏 -14465；hybrid 70 局 rating 2509.0、P10 -1152.8、最坏 -6460。
- 推断：Yarn-first fallback 可能稳健；Pizza/Smoothie 扩展仍需同种子配对反证。

### C-KAGG-002 — v43 触发与同步机制已核清（F/I）

- 项目线回执时间：2026-09-09；来源为公开 v43 notebook 正文与本地静态审计。
- 事实：Yarn-first/Yarn-second 首次动作分歧分别在 step 88/153；三个子控制器每步都接收 observation，仅当前专家输出；103/128 是 8 seeds×8 public agents×双座位本地证据。
- 判断：可迁移的是可见事件后分支、分支前逐动作一致和持续状态同步；公开 tape 与 103/128 不能当本项目策略或 LB 保证。
- 下一步：KG-002 结案后，只做 component policy 是否有跨步状态和逐动作前缀一致性审计；不复制动作轨迹。

### C-KAGG-003 — Pizza/Smoothie fallback 扩展被配对反证（N）

- 本地来源：`kaggriculture/reports/experiment_ledger.md`；判决：KG-002 停止、不提交。
- 事实：每个版本均完成 432 局（24 seeds×9 opponents×双座位）。相对 KG-001，Y+Pizza/Y+Smoothie/三店组合分别净少 13/3/16 计分点，mean margin -454.16/-34.49/-488.65；seed-cluster bootstrap 的 score-rate delta 95% 区间上界均为 0。
- 尾部：Pizza 目标 41 局从 37-4-0 变为 26-0-15，P10 +7515→-1902、worst 0→-12082；Smoothie 目标 26 局从 24-2-0 变为 22-0-4，P10 +1310→-344。基线目标分支原本零败，扩展只新增失败。
- 结论：远端非配对首店胜率是错误方向；Pizza/Smoothie 家族永久冻结。下一实验仅允许 Yarn-second 可见条件与前缀/state-sync 分开测试。

### C-ARC-001 — 权威 Kaggle 数据版本差异（F）

- 本地来源：`arc2_paper/README.md`、文件哈希和任务比较结果。
- 事实：training 1000/1000 与 GitHub 相同；evaluation 的 120 个 ID 相同，但 114 个完全相同、4 个 test-input 变化、2 个 train 变化；测试输出数 167→172。V175 在权威 evaluation 上 0/172。
- 含义：后续实验以 Kaggle 文件为唯一权威输入，旧 GitHub 结果仅作历史对照。

### C-ARC-002 — 两赛已加入，development 48 正在运行（F，纠错）

- 权威来源：`arc2_paper/paper/results/registration_snapshot_2026-09-09.json`、`arc2_paper/official/competition_files/competition_manifest.json`、`arc2_paper/kaggle_runs/development_stable_v2/run_manifest.json`。
- 事实：2026-09-09 04:36:59 CST 的注册收据显示 ARC-AGI-2 与 Paper Track 均 `user_has_entered=true`；05:15:49 的 Team 页面快照显示两边 team 均为 `Jiayi Du`、sole member/leader `jahyee`。线程稍早的 `userHasEntered=False` final 已过时，不得据此请求用户重复 Join。
- 运行：private run `348340917` 于 04:31:34 开始，L4x4、internet=false、frozen development 48；05:20:50 仍为 RUNNING。单一问题是 checkpoint consensus + best-distinct 是否在不改 attempt1 的条件下优于 KGMon top2。
- 守卫：覆盖完整、grid 有效、六小时内完成，development 至少新增 1 个输出才进入 sealed holdout；fallback 为 unchanged KGMon NVARC top2。
- 资产：五折 manifest SHA-256 `c6112e37b29296b0139764de43611f01475d421cad5da7cd05f849d700a07a99`；5 折各 200，四个 quartile 各 50，总计 1000 唯一任务。canonical ARC-AGI-1 pin 为 40 位 `399030444e0ab0cc8b4e199870fb20b863846f34`。
- 边界：注册、哈希与运行中状态不证明性能；等待同一 run 的终局收据，不重启。

### C-ARC-003 — frozen48 终局为 runtime failure，不是 selector 零结果（F/N）

- 权威来源：`arc2_paper/kaggle_runs/development_stable_v2/run_manifest.json`、`analysis/benchmark_receipt.json`、`analysis/paired_summary.json`；run `348340917` 于 2026-09-09 05:47:22 CST COMPLETE。
- 事实：48 tasks/50 outputs，wall 上界 4,548 秒、schema 全有效；KGMon、portfolio、probmul、agreement 都为 48/50=0.96，四个策略文件同一 SHA-256 `f88458667319a86fcc29384d1b9d1db09e762671671ccbcf9d08b04bd23b27d0`，attempt1/attempt2 改变均为 0，20,000 次 paired bootstrap CI=[0,0]。
- 失败边界：TRM 在 47.88 秒、optimizer 初始化阶段 return code 1，未生成候选；`AdamAtan2(lr=0)` 触发当前包的 `assert lr > 0`。题 `e619ca6e` 在 1,219.1 秒只完成 3/4 decode，故 `zero_timeouts=false`、`all_decodes_complete=false`。development gate FAIL，不进 sealed holdout。
- 结论：本轮只证明 fallback 与收据链有效、候选多样性为零；不能据此否定 selector。
- 最小实验：AdamAtan2 构造只改为 `lr=config.lr`，保留每步 scheduler；同 Kaggle image 先做 1-task/1-step smoke。通过后同 frozen48 只重跑一次，先看 TRM 独占解与 oracle 是否至少 +1 output。
- 成本/风险/停止：低 smoke+一次 L4x4；风险为 checkpoint/puzzle embedding/ABI/超时。smoke 失败不重跑；TRM 无独占解、oracle<+1 或 coverage/grid/6h 失败即停止 selector，保留 KGMon。

### C-ARC-004 — lr 修复越过 constructor，但 smoke 暴露独立日志兼容故障（F/N）

- 权威来源：`arc2_paper/paper/results/trm_adam_lr_compat_smoke_failed_2026-09-09.json` 与对应 Kaggle kernel/log；private、internet off、只用公开训练题 `bc1d5164`，solutions 未读取。
- 单一变更/事实：AdamAtan2 constructor bootstrap 从 `lr=0` 改为 `config.lr`，原 per-step scheduler 保持。checkpoint_loaded=true、optimizer_constructed=true，说明原断言已修复；但首个 optimizer step 前，离线 wandb 改写留下 `print(payload, step=0)`，触发 TypeError。kernel ERROR、rc=1、无 checkpoint/grid/submission。
- 边界：这是 runtime progression，不是 accuracy、coverage、diversity 或 selector 证据；full48 与 sealed 均未授权。
- 下一最小动作：版本化 v2 已本地冻结，只把该错误改为接受 payload/optional step 的 stdout helper，保留 lr 修复；仍为 1-task/1-step solution-blind smoke。外部私有 kernel 上传属于代码/数据 egress，必须先有用户明确批准。
- 停止：v2 任一 guard 失败，永久停止 TRM 兼容路径，不做第三个补丁/full48/sealed；通过后才允许一次 frozen48 重跑。

### C-ARC-005 — V2 已在 safety boundary 前 push；本地 guard 通过但远端终态未知（F/I）

- 权威来源：`arc2_paper/kaggle_runs/trm_wandb_log_compat_smoke_v2/local_preflight_receipt.json`（SHA-256 `60d6c77b…`）、`paper/results/trm_wandb_log_compat_smoke_v2_local_behavioral_regression_2026-09-09.json`。
- 外部边界：private kernel version 1 已在后来 local-only boundary 前 push；最后获授权观测为 2026-09-09 06:27:41 CST `RUNNING`，06:34:25 safety boundary 后未查询、下载、重跑或上传，current terminal status=`UNKNOWN`。
- 本地事实：V2 只把坏的 `wandb.log→print` 改为接受 `payload, step=None` 的 stdout helper；V1 的 positive `config.lr`、scheduler、模型、checkpoint、task/data/RNG/seed、1 epoch/1 expected step 均不变。AST/compiler、logger、lr anchors、scheduler path、private/offline、one frozen task、no solutions 与 fail-closed guards 的 behavioral regression 全过。
- 证据边界：本地 regression 不证明 Kaggle 已完成、到达 step1、生成 grid、return code=0 或 accuracy；不得写成 passing smoke。
- 下一动作/停止：不得重复上传。只有用户明确批准后，先只读查现有 kernel status 并下载 artifacts；任一 runtime guard 失败即永久停止 TRM route，不做第三补丁/full48/sealed。

### C-ARC-006 — V3 在 development 达到 50/50，但属于 post-hoc rule fit（F/I）

- 权威来源：`arc2_paper/paper/results/exact_overlay_v3_posthoc_development_2026-09-09.json`；combined submission SHA-256 `6ef6f663…`。
- 单一变更：保留 attempt1；仅当固定 V176 rule 在所有 demonstrations 精确且唯一时替换 attempt2。两个规则分别把 development 从 48/50 提到 49/50，组合后 50/50、attempt2 incremental=3、changed outputs=2、ambiguous=0、harm=0、schema valid。
- 边界：两条规则都是检查 development misses 后导出；50/50 只证明实现与 source-corpus complementarity，不是 unseen、sealed、public-eval 或 competition 结果。
- 决策：冻结本地候选，不查/推 Kaggle、不打开 sealed holdout；只有 runtime gates 全过且另获明确授权，才按预注册一次性评估。论文必须显式标记 post-hoc derivation。

### C-ARC-007 — Writeup 审计已能拒绝训练成绩，但草稿远未 final-ready（F）

- 权威来源：`arc2_paper/paper/tools/audit_writeup.py`、`paper/manifests/writeup_evidence_contract_v1.json` 与 `paper/tests/test_writeup_audit.py`；2026-09-09 本地实跑 auditor 与 regression 均通过。
- 当前草稿：1,217 whitespace-delimited words、9 numerical claim bindings、10 public links、0 training/development performance mentions；但有 3 placeholders，Accuracy=`missing`，Completeness/Novelty/Progress/Universality=`partial`，`final_ready=false`。
- Fail-closed 证据：regression 注入 `Development accuracy was 48/50` 后必须报 `train_performance_reported`；FINAL 模式还拒绝 placeholders、unsupported dimensions、缺 platform word count 与缺 notebook/submission/source/cover/project/Writeup bindings。
- 结论/停止：DRAFT pass 只证明结构和证据绑定，不是 Accuracy、submission 或 publication readiness。V2 runtime、sealed/public-eval 与所有最终绑定未齐前不得改为 FINAL。

### C-ARC-008 — 三阶段合同结构通过，但所有实证阶段仍未授权（F）

- 权威来源：`arc2_paper/paper/manifests/three_stage_pipeline_v1.json`、`audit_three_stage_pipeline.py`、`stage_receipt_v1.schema.json`；本轮独立重跑四项均 exit 0。
- 事实：该快照的 active audit `passes=true`、`pipeline_complete=false`、runtime smoke=`UNKNOWN`；development=`PENDING_PREREQUISITE`，sealed/competition=`NOT_AUTHORIZED`，当时 next action=`AUTHORIZED_READ_ONLY_RUNTIME_SMOKE_STATUS`。主 pipeline regression、7 个 active-boundary tests 与 Draft 2020-12 schema regression 全过；当前动作已由完整性反例改写，见 C-ARC-015。
- 守卫：labeled stages 强制 task/output、attempt 分解、七类 family、runtime/memory/failure、format 与 artifact hashes；competition 强制 local correctness/per-family solved 为 null，只允许 Kaggle aggregate score、submission/kernel/version/观察时间与固定 reference gap，禁止 leaderboard 选策略。
- 边界/停止：结构 PASS 只证明顺序与绑定，不是 smoke、accuracy、holdout 或 submission 证据。用户未明确授权前不查询 Kaggle；runtime terminal receipt 未通过就不得进入 development。

### C-ARC-009 — 官方日历与 Paper 报告规则已冻结，日期冲突按更早值执行（F/I）

- 权威来源：`arc2_paper/paper/results/official_arc_prize_deadline_recheck_2026-09-09.json`，SHA-256 `98f84b6622b4bae369e007833e0c76e7f9dceb536d3f7c27b0b0e7711ffe844c`；公开页为 <https://arcprize.org/competitions/2026>、<https://arcprize.org/competitions/2026/arc-agi-2>、<https://arcprize.org/competitions/2026/paper>。本轮未查询 Kaggle。
- 日期：公开 ARC Prize 页列 competition submissions 2026-11-02、Paper 2026-11-08；旧 authenticated Kaggle snapshot 列 ARC 2026-11-02 23:59 UTC、Paper 2026-11-09 23:59 UTC。ARC 页面没有精确时区，Paper 相差一天；内部暂用更早的 11-08，终局需另获授权后复核。
- 冻结日程：D-21 架构冻结 10-12；D-7 Notebook/依赖冻结 10-26；D-3 起只允许验证和最终选择 10-30。公开页还要求 ARC-AGI-2 每个 test input 两个预测、prize artifact 在提交截止七日内公开。
- Paper 边界：必须绑定实际 Kaggle code submission；结果来源应为 Kaggle leaderboard/public evaluation；不得报告 train-set performance。当前 Writeup auditor 已报告 1,217 words、9 bindings、0 training/development mentions；3 placeholders、Accuracy missing、`final_ready=false` 仍未解除。
- 当时的独立验证：完整 `arc2_paper/paper/tests` 18/18 通过。它证明 deadline receipt、schema 与 fail-closed 工具一致，不证明 V2 runtime、accuracy、sealed/competition 或 publication readiness；后续新增 terminal-receipt tests 后的当前基线见 C-ARC-010。

### C-ARC-010 — V2 本地 API 路径与 terminal receipt 入口已加固，但远端仍 UNKNOWN（F/I）

- 本地 API 路径：`artifacts/trm_optimizer_logger_micro_smoke/local_micro_smoke_receipt.json` SHA-256 `49ee14c2f49db93aaca6ecd2e138d735c3b159c1b53f8db3818f4f3a5d117765`。在 CPU 上用随候选冻结的 `adam_atan2_pytorch==0.2.4` 实际完成正学习率构造、scheduler 覆盖、一次 optimizer step、参数更新和带 `step=0` 的 offline logger；10/10 guards 通过，连续回放确定。
- 局限：未实例化 TRM、未加载 2.16 GB checkpoint，未执行 CUDA、distributed、数据构建、evaluation 或 submission export；不能替代 Kaggle one-task/one-step smoke。
- terminal 工具：`build_runtime_smoke_receipt.py` SHA `b3a29a40001ec3d43e1c544cd4218d81fcd7abc9d00175bd5521203cfdda7046`，`commit_runtime_smoke_receipt.py` SHA `1385cdb7092e27e12ff863366ee051eac1d3258472ddbfe7b21d0164dff86b0a`，test SHA `13ef4575871a3c3e5c80af4d5191678d1307d1881d7d1475e86d559856bfdf71`。它们只转换已获授权的终态观察，重验 V2 notebook/runtime/metadata/source/artifact 哈希，并拒绝非终态、身份漂移、缺 guard、源漂移与项目外路径；commit 只更新 smoke prerequisite。
- 独立验证/边界：该快照的完整 paper suite 22/22 通过；active audit 当时仍 `passes=true`、`pipeline_complete=false`、runtime smoke=`UNKNOWN`、development=`PENDING_PREREQUISITE`、sealed/competition=`NOT_AUTHORIZED`。用户未授权前不得查询 Kaggle；当时 next action 为 `AUTHORIZED_READ_ONLY_RUNTIME_SMOKE_STATUS`，随后 holdout 完整性反例已将当前动作改写，见 C-ARC-015。

### C-ARC-011 — 公开 Kaggle 与旧账户快照相互印证，但仍和 ARC Prize overview 差一天（F/I）

- 权威来源：`paper/results/public_kaggle_deadline_recheck_2026-09-09T184121+0800.json` SHA-256 `1ac2df00410908d1c00127539bff8571e599f5d8edc35b98c8c8cad296ab0136`；公开 Kaggle 官方 competition pages 为 <https://www.kaggle.com/competitions/arc-prize-2026-paper-track/overview/abstract> 与 <https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/overview>，观察时间 2026-09-09 18:41:21 CST。consistency regression SHA `15fc34157136accf737d74b69340575fa6401bcc96bab81805eb0bb723defe7c`。
- 事实：公开 Kaggle 显示 Paper final `2026-11-09 23:59 UTC`，ARC-AGI-2 entry/team merger `2026-10-26 23:59 UTC`、final `2026-11-02 23:59 UTC`；与 `registration_snapshot_2026-09-09.json` 的旧 authenticated snapshot 精确一致。
- 冲突/判决：ARC Prize overview 仍写 Paper 11-08。因此提交平台 controlling deadline 记 11-09 23:59 UTC，但内部 conservative hard stop 继续 11-08 23:59 UTC，不用多出的一天扩实验。
- 授权边界：本次只读公开索引，authenticated Kaggle、private kernel status、artifact download、mutation、submission、sealed holdout 均 false；它不解除 V2 smoke UNKNOWN，也不构成运行/分数/发表证据。

### C-ARC-012 — all-stage measurement bridge 已补齐 competition 隐藏标签边界（F/I）

- 权威绑定：`paper/tools/build_stage_measurement.py` SHA-256 `eabcafd16732ca4f602706f15165107ccc59bc394a544046146dc614fd58521f`；`competition_observation_v1.schema.json` SHA `3b7033307271c449abfda179fbbee1883fad20bd9df35e4a8e0fcc6a5ac13f1c`；measurement-bridge 快照时的 three-stage contract SHA `97517c16c598dc5ffd46a67ff537fedf5b04611c4820898930960eecb901fa3d`，后续 current binding 见 C-ARC-013。
- 功能证据：builder 只接受 contract 结构通过、目标 stage 已 `RUNNING`、frozen notebook/hash/scope 一致的完成工件。有标签的 development/holdout 独立重算 attempt1/attempt2、anchor/method、runtime/failure 与 demonstration-only 七 family；competition 只接受 COMPLETE 的只读 Kaggle submission receipt，逐文件重哈希并把本地 correctness/delta 全设为 null。
- 独立验证：competition schema、real Stable-V2 replay + synthetic labeled/competition measurement、three-stage transition 三个 standalone regressions 全 PASS；既有 paper unittest 22/22 仍 PASS。test-output 注入、hidden correctness 新字段、错误 notebook/hash/scope、缺 submission ID 与 leaderboard-driven selection 都 fail closed。
- 当时审计：`passes=true`、`pipeline_complete=false`、smoke=`UNKNOWN`、development=`PENDING_PREREQUISITE`、sealed/competition=`NOT_AUTHORIZED`；next action 当时仍是用户授权后的 `AUTHORIZED_READ_ONLY_RUNTIME_SMOKE_STATUS`。Paper readiness 当时结构通过但 `final_ready=false`，有 8 类 blocker。该桥不查询 Kaggle、不启动 stage、不提供 accuracy/score/submission；当前 holdout 污染与第 9 类 blocker 见 C-ARC-015。

### C-ARC-013 — one-stage authorization bridge 把每次外部运行收缩成独立用户收据（F/I）

- 权威绑定：`paper/tools/authorize_stage.py` SHA-256 `9ba09d4c7ffb3a647105e9897727026ac4938c8461f3903fc471d442a6ff29d0`；authorization schema SHA `a8e457a6026b0a90e6c5e9b9cddf3d37eb8ae1831ffa01fd11e96de58bd7db7b`；authorization-bridge 快照时 active contract SHA `f05cea35ce49f83dccd785fc80c73903ad17ae6b25c48cef0e6bfa26802426ad`，当前 contract 见 C-ARC-015。
- 机制：只在 pipeline 当前结构通过、该 stage 正是唯一 next eligible action、前置 terminal/stage receipt 已完成且哈希绑定、用户收据晚于前置完成时间、contract-before hash 与冻结 notebook 精确一致时，原子写入一个 stage 的 `RUNNING` 与授权绑定。收据固定 `one_run_only=true`、`public_leaderboard_used_for_selection=false`、`future_stages_authorized=false`；工具输出 `external_action_performed=false`，本身不运行 Kaggle。
- 独立验证：完整 paper unittest 22/22，加 competition schema、measurement builder、three-stage、stage authorization、authorization schema 五个 standalone regressions 全 PASS；过早/旧 contract、错误 action、leaderboard selection、替换 notebook、项目外 receipt 与 smoke UNKNOWN 下越级均 fail closed。
- 当时边界：schema 和工具不是用户授权；该快照的 next action 为 `AUTHORIZED_READ_ONLY_RUNTIME_SMOKE_STATUS`，smoke `UNKNOWN`、三个实证 stage 均未运行。随后完整性审计新增第 9 类 blocker 并改写当前 next action，见 C-ARC-015。

### C-ARC-014 — 失败 stage 现在会原子封存并永久阻断当前 candidate 的后续链（F/I）

- 权威绑定：`paper/tools/commit_stage_failure_receipt.py` SHA-256 `dc453dc53227aca8ff46819ab7b8c5ae77af6709ee95a6025b7f3e66af247771`；commit regression SHA `f61b32c17615f28206457b77af90aa25eed5dd75bf13a3f8afc835696b55aaed`；三阶段审计器当前 SHA `bc127447b35518df7f59e7c2247f061230e8a7e4023399a64448e9ba83f376ba`。
- 机制：只接受 `RUNNING` 且尚无 receipt 的单一 stage；重验 stage/candidate/frozen notebook、normalized failure schema、authorization 后的 started/completed time 与项目内路径，然后原子写入 `FAILED` 和 receipt hash。提交后 `pipeline_complete=false`，唯一一下动作为 `STOP_CANDIDATE_AND_VERSION_FROM_FAILURE_RECEIPT`，later stage 不会因失败而自动获批。
- 独立验证：`test_commit_stage_failure_receipt.py` standalone PASS，完整 paper unittest 22/22 仍 PASS；三个 stage 的合法失败、pre-authorization start、wrong stage、COMPLETE 冒充失败、项目外 receipt、non-RUNNING stage 与 active UNKNOWN pipeline 均覆盖。工具返回 `external_action_performed=false`。
- 当前边界：active pipeline 没有进入 `RUNNING`，因此没有 failure receipt 被消费，状态仍 smoke `UNKNOWN`、development pending、sealed/competition unauthorized。该工具只保存未来失败的因果历史，不是失败已发生或允许重跑的证据；当前最先动作已由 holdout 完整性反例改为替换污染 holdout，见 C-ARC-015。

### C-ARC-015 — V3 holdout 虽 ID-disjoint，却已被全语料 solution 审计污染（F/N）

- 权威来源：`arc2_paper/paper/results/v3_holdout_integrity_audit_2026-09-09.json` SHA-256 `d04c5599a17bb23e2cb941daf258886d8e4263c86ba80a764ae2617b6e4f5333`；audit tool SHA `9b63c513d3b0d2477f1fb5fd5275691b14e1d65ebf88722a1e601c381a21eb99`。审计自身 `holdout_solutions_read=false`、`task_ids_disclosed=false`、`external_actions=false`。
- 事实：历史 source audit 加载全部 1000 个 training solutions；V176 选中的 2 个任务都在 development。拟定的 48-task/49-output holdout 与 development task IDs 不重叠，但 V176 在该切片上 0 个 selected task、会“全 abstain”在运行前已经可知。因此它不再是 method-unseen generalization evidence。
- 判决：状态 `CONTAMINATED_FOR_V176_GENERALIZATION`，promotion 被 `BLOCK_V3_HOLDOUT_PROMOTION_UNTIL_NEW_UNTOUCHED_HOLDOUT`。禁止从该切片声称 V176 overlay contribution、两条规则的新题泛化、Progress 或 Novelty；仅允许 unchanged parent runtime、format 与 artifact-integrity 结论。重洗同一 1000 题不能恢复封存性。
- 当时门禁快照：three-stage contract SHA `1fedbc618ce1377cfd877385297cf3f4f8da6da4062f83c834fc5712ed1e52e3`，auditor SHA `8e94757b42dff2859d2e47b900f6cc22a7f3a8e25443bd8bdb38d23aa2e200e4`；审计结构 `passes=true`、pipeline incomplete、smoke UNKNOWN，当时 next action=`REPLACE_CONTAMINATED_HOLDOUT_BEFORE_EXTERNAL_RUN`。submission-readiness manifest SHA `bf3534f56d0e8ddc1094e34b29f16398a142db5da9c29c15f0b1406006e25de5`，结构通过但 `final_ready=false`、9 类 blocker。当前负面转向见 C-ARC-016。
- 独立复核：修订后完整 unittest 23/23 PASS；holdout-integrity、three-stage、stage-authorization、failure-commit 四个 standalone regression 全 PASS。没有 Kaggle 查询、下载、运行、提交或 sealed solution 访问。
- 当时下一动作/停止：只有在 V176 与选择规则冻结后、solutions 从未被开发流程读取的真正新 labeled corpus 才能重启泛化实验；否则删除 V176 泛化/Progress/Novelty 主张并把论文转为 systems negative。语料审计现已触发后者，见 C-ARC-016。只读 V2 terminal receipt 仍可回答 runtime，但不能修复这一证据污染。

### C-ARC-016 — 五个既有带标签语料均已被父系统使用，当前无合格新 holdout（F/N）

- 本地权威来源：bundled parent source README SHA-256 `c823d8c590d6a4f20a3d9f5ac2384fbdc921035f1f206a5029d34eb5e1ac1b68`；V175 exact-rule receipt SHA-256 `62a2c6ab0119441a9526ebb7b0c8161935600c80a1646ce7f22870a17ca076d1`。
- 决定性事实：收据覆盖 ARC-AGI-1 training 400/416 outputs、evaluation 400/419，ARC-AGI-2 training 1000/1076、evaluation 120/172，以及 ConceptARC 160/480，合计 2,080 tasks / 2,563 outputs。README 明示规则已在官方 ARC corpora、重复分区与 ConceptARC 上测试；ConceptARC 更是 160/160 tasks、480/480 outputs 全覆盖。因此这五组均不能作为规则冻结后的 method-unseen evidence，重排也无法恢复封存性。
- 公开一手边界：ConceptARC 官方仓库确有 16 groups×10 tasks、每题 3 test inputs，但已被父系统完整使用；1D-ARC 是 18 类一维合成变换，MiniARC 使用不同 playground/object interface。后二者及社区/合成语料可做机制性 domain-shift stress test，却没有可验证依据支持 ARC-AGI-2 目标分布等价或 V176 主泛化。
- 判决/最小动作：截至当前没有找到“合规、带标签、冻结后 solutions 对项目与上游源码均未见、且 ARC-AGI-2 可比”的语料；立即转 systems-negative，删除 V176 generalized contribution、Progress 与 Novelty，不运行 selector/holdout performance。V2 smoke 即使以后获用户授权，也只证明 runtime/format/artifact integrity。
- 重开指标/成本/风险/停止：取数前冻结 solver、规则、指标、纳入/排除与许可；要求第三方独立创建、content/hash overlap=0、license compatible、solution-access history=0，并只运行一次。成本是获取并审计真正独立语料；风险是把域外或历史已见任务包装为主分布 evidence。任何历史 solution access、内容重叠、许可不清或分布不可比即停止；1D/Mini/community 必须标作 `domain-shift mechanistic stress test`。

### C-POKER-001 — PU 标签语义与高 CV 风险（F/I）

- 本地来源：`poker/work/audit.json`、`poker/work/model_diagnostics.json`。
- 事实：标签为 positive/unlabelled；当前 group CV Pair AP 0.946934，训练审计为 1860 条标注、372 positive。
- 推断：分数可能是真实行为信号，也可能受玩家重复、pair 结构或合成器代理影响；需玩家连通分量 OOF。

### C-TRAFFIC-001 — Task 1 的双重权重与 queue 边界（F/I）

- 本地来源：`traffic/README.md`、官方仓库快照和 artifact ledger。
- 事实：State/Queue/Physics/ODME 权重为 35/30/15/20；Task 3 读取 Task 1，故 Task 1 影响 50% 总分。V32 公开工件 6,985,307 行，公开分数 0.71846。
- 推断：queue 的“距最后历史时间 ≥30 分钟”实现可能把 +25/+30 混为正例；必须先做逐 horizon 单测。

### C-TRAFFIC-002 — 拓扑/复杂 Queue 被否定，off-by-one 单点晋级（F/I）

- 项目线回执时间：2026-09-09；状态：本地确认，待官方 key 与远端验证。
- 事实：等成本确认集否定 Task 1 拓扑族；复杂 Queue 趋势/冲击波版也失败。最小 off-by-one 候选共 174,000 行，仅 160 行由 1→0，覆盖 80 个 onset 窗口、每窗移除两个 T+25 正例，其余 173,840 行不变。
- 判断：保留最小 delta，冻结两个失败方法族；它符合“单因果点、可定位、可回滚”，但尚不能称为 LB 增益。
- 下一步/停止：官方自然键与格式守卫全过后才占一个提交槽；总分增益 <+0.015 即归档，不用组合补丁挽救。

### C-POKER-002 — E003 已预注册泄漏与退化门（F）

- 项目线回执时间：2026-09-09；状态：运行中。
- 事实：看结果前已写明 Pair AP 最多下降 0.01、known-positive 相对 unlabeled 中位百分位至少提高 0.02、最差折 AP 最多下降 0.03；unknown 产物明确标记 `label_status=unlabeled` 且无 label 列，候选按共享手数阈值构造，不解析 ID/行序。
- 判断：这是一份合规的预注册收据，不是性能结果；待 400 个 pool 分块运行完成后升级或否定。

### C-POKER-003 — E003 主指标上涨但仍按门槛失败（N）

- 项目线回执时间：2026-09-09；判决：不提交。
- 事实：confirmed Pair AP 0.94839→0.95437，最差折微升；但同池 known-positive 相对 unknown 的中位百分位在 anchor/E003 上均为 1.0，增量为 0，未达到预注册 +0.02。
- 结论：主指标上涨不能覆盖迁移性门失败；饱和统计也不能继续承担 selector 角色。
- 下一步：审计开发 60% 与 evaluation 40% 的 exposure/累计量漂移，建立时间截断 pseudo-eval；累计量特征必须与按机会数/每100手归一化版本对照。
- 停止：截断后排序/校准不稳则先修 exposure，不继续堆 PU 模型；E003 永久保留为负结果。

### C-POKER-004 — 全特征 pool×phase 百分位化也失败（N）

- 本地来源：`poker/work/E004_pool_rank_validation.json`；判决：`preregistered_gate.passes=false`，不提交。
- 事实：confirmed Pair AP 0.9483865→0.9426666（-0.00572），worst fold -0.00997，P95 tail +0.00269；这些单项在容忍度内。但 unlabeled→evaluation score KS 从 0.0612865 升到 0.0823127，fraction reduction=-34.31%（要求至少 +30%），且 evaluation score 与 shared_hands 的绝对 Spearman 0.102147，略超 0.10。
- 合规：unknown ground-truth labels assigned=0。
- 结论：把全部 95 特征做相对 rank 会抹掉有效幅度信息，却没有修复 score-domain drift；该表征冻结。
- 下一步/停止：只把已识别的 exposure-sensitive counts 转为 per-opportunity/per-100-hand rate，其他特征/learner/folds 不变；若 KS 不降 30% 或 |Spearman|>0.10，停止 exposure-normalization family。

### C-TRAFFIC-003 — off-by-one 候选通过全量提交门禁（F/I）

- 项目线回执时间：2026-09-09；状态：已开始单一问题远端提交，分数待定。
- 事实：锚点与官方 key 的 6,985,307 个 ID/任务映射全量一致；候选无缺失、重复、非有限值或任务域错误。精确 160 行变化，全部为 queue_pred 1.0→0；State/Physics/ODME 逐字节不变。
- 候选 SHA-256：`7e5c790f917bfb112d572aeab520edc611174c3a98b68ce23190a06c297521da`。
- 判决线：公开总分必须达到 0.73346（0.71846+0.015），否则回退 V32 并停止该 Queue 家族。

### C-TRAFFIC-004 — 160 行修复获得可归因远端增益（F）

- 本地来源：`traffic/artifacts/submission_ledger.csv`、`traffic/artifacts/experiment_ledger.csv`、`traffic/artifacts/campaign_status.json`。
- 事实：submission `56107311`，Public 0.74210；相对 V32 0.71846 提升 +0.02364，超过预注册 +0.015 继续门。提交 SHA-256 `7e5c790f917bfb112d572aeab520edc611174c3a98b68ce23190a06c297521da`。
- 因果边界：6,985,307 行中仅 160 个 queue_pred 从 1→0；State/Physics/ODME 与其他 Queue 行逐字节不变，因此本次 public 增益可归因于 horizon off-by-one 修正。它不证明复杂 shockwave 或拓扑族有效。
- 后续：冻结为新锚点；全量数据/哈希完成后只做分层失败审计，不能在成功邻域继续堆 Queue 补丁。

### C-KAGG-004 — Yarn-second 路由反事实进入严格验证（F/I）

- 本地来源：Kaggriculture 项目线的 route0/route1 动作差分与历史配对收据；状态：KG-004 运行中。
- 事实：现有 shop router 在前两家商店含 Yarn 时于 step 144 选择 route1；route0/route1 在 step 0–167 动作完全一致，首次可能分歧为 step 168。历史 8 个 Yarn-second 双座位单元中，route1 为 0-0-8、route0 为 2-0-6；6 个改善、2 个恶化，mean margin delta +2205.5。
- 候选：只在可见 Yarn-second 条件保留 route0；KG-001 的 Yarn-first 行为不变。由于 public/shop controller 从 step 0 即不同，不做 late switch 到 public，避免状态不同步。
- 最小实验：seeds 15001–15024 × 9 opponents × 双座位的开发矩阵；通过后才允许至少 32 个新种子确认。
- 指标/停止：总计分率必须严格提高、任何 opponent 不得净退化、P10 delta ≥-500、worst delta ≥-2500、Yarn-second 命中至少 8 且目标失败减少至少 30%；任一门失败即停止，不提交。

### C-KAGG-005 — KG-004 在 432 局被灾难性反转（N）

- 权威来源：`kaggriculture/reports/compare_dev15001_15024_yarn2_route0_vs_v1.json`、`kaggriculture/reports/experiment_ledger.md`；两边各 432 局（24 seeds×9 opponents×双座位），全部 `DONE`。
- 因果范围：仅 66 个“首店非 Yarn、第二店 Yarn”单元变化，其余 366 完全不变。命中层 KG-001 为 52-8-6、score rate 84.85%；route0 候选为 38-0-28、57.58%，净少 18 计分点。
- 尾部/全局：目标 P10 0→-11,356，worst -5,219→-18,616；全局 mean margin delta -1,155.61。24 seed cluster 的 20,000 次 bootstrap：mean delta 95% `[-2342.24,-181.51]`，score-rate delta 95% `[-9.26%,-0.23%]`，全负。
- 结论：最初 8 单元的 route0 正向是假阳性；KG-004 不进确认、不提交，Yarn-second route0 冻结，保留 KG-001/original route1。
- 下一动作/停止：只读寻找与已冻结商店身份无关、在至少两类对手和双座位重复的 step168 前可见状态失败桶；没有这种桶就不生成新 guard。

### C-KAGG-006 — KG-005 的 TOMATO-heavy late switch 被直接反证（N）

- 权威来源：`kaggriculture/reports/experiment_ledger.md`；seeds 16001–16024 × 9 个公开对手 × 双座位，两边各 432 局，全部 `DONE`，trigger mismatch=0。
- 单一干预：首店为 Pizza、到 step576 且公开对手农场 `TOMATO>=12` 时，从同步商店 continuation 永久切到 public controller；只读取当前公开状态，不用身份、种子、未来商店或私有信息。候选 SHA-256 `893f236d...`，回退 KG-001 SHA-256 `3c94aa53...`。
- 事实：只有 4 个目标单元触发，低于预注册最小支持 8；目标层 KG-001 为 4-0-0、mean margin +6,751、worst +6,691，候选为 0-0-4、mean -10,191、worst -10,422，目标 mean delta -16,942。其余 428 局逐局相同；全局少 4 计分点、score rate -0.926pp、mean margin -156.87，24-seed cluster bootstrap score-rate delta 95% `[-2.31%,0]`。
- 结论：公开的 TOMATO-heavy 状态是相关信号，不是 continuation 失效的因果证据；冻结该阈值/late-switch 家族，不确认、不提交、不调阈值。
- 下一动作/停止：先只读核对 KG-000 与 KG-001 在完全相同 `(opponent, seed, seat)` 键上的互补性，报告各槽 W/T/L、独占胜局、union coverage、P10/worst 和错误；共享支持不足才补一批固定双锚点配对仿真。没有独占胜局或尾部变差即保持现有两槽，不生成第三代理。

### C-KAGG-007 — 两条 active submission 跨过 100 局成熟门（F）

- 权威来源：`kaggriculture/reports/remote_maturity_gate_100_2026-09-09.json`；源摘要 SHA-256 `8188d401986b4d1ca39604020d5d675ceee6797a468d434b3a154b713f022be5`。同步只读，不记录隐藏 seed、不读对手私有日志，未执行提交变更。
- 事实：public `56102094` 为 101 局 70-6-25、计平局胜率 72.28%、rating 2325.0、mean margin 10,886.05、P10 −3,268、worst −14,465；hybrid `56102097` 为 100 局 74-7-19、77.50%、rating 2584.2、mean 9,783.93、P10 −1,393.1、worst −20,432。两者全部 `DONE`、零 stderr，最大动作时延分别 0.205432/0.249954 秒。
- 边界：两条 live 样本并非同 `(opponent,seed,seat)` 配对，不能据此声称 union 或因果增益；但在官方 best-of-two team rule 下，hybrid 可作为当前较强结果，public 可保留独立策略与更好的已观察单局下界。
- 决策：继续保留 public+hybrid 两槽，不上传、替换或停用；没有第三代理通过本地保护门。
- 下一动作/停止：仅只读监控 W/T/L、rating、P10/worst、双座位、运行错误与时延。短期 rating 波动不触发换槽；没有先通过固定配对保护门的新候选，就不再开策略搜索或提交。

### C-KAGG-008 — KG-006 只改最后市场结算，已进入严格开发（F/I）

- 权威来源：`kaggriculture/reports/experiment_ledger.md` 与 `prefix_audit_smoke_kg006_16999.json`。
- 事实：100 局公开回放中 public/hybrid 有 34/11 局在终局留下可卖库存；包括 public 的 −11,037 局留下 29 WHEAT、−2 局留下 2 WOOL，以及 Yarn 路径 10 WOOL 只请求卖 8。官方环境审计确认 step718 是最后行动、单位动作后执行市场、final reward 只取 cash，成功 SELL 每单位以公开价≥1 增现金，718 不触发定期消费。
- 单一干预：step0–717 完全保持 KG-001；step718 保留 farmer/hands 和既有 market 顺序，只把已有 SELL 数量提到足量，并按固定产品序填充剩余最多 10 个 market slots。只用我方公开库存，不用身份/seed/私有状态。
- 前缀 smoke：seed16999、对 public 双座位全部 `DONE`，first diff min=718，step0–717 compatible。
- 最小实验/门：17001–17024×9 opponents×双座位；总体计分严格提高、各对手不净少、P10 delta≥−500、worst≥−2500、目标命中≥8且失败减≥30%、全 `DONE`。失败即停；通过才进不重叠≥32 seeds 确认，当前不提交。

### C-KAGG-009 — KG-006 现金增益成立，但未产生任何胜分（F/N）

- 权威来源：`kaggriculture/reports/compare_dev17001_17024_terminal_sweep_vs_v1.json`；comparison SHA-256 `a87ac48c54a220696946f224ab51967d32f4a68006cacb980203f67d646411a4`，baseline/candidate report SHA-256 `03b8f7ea…` / `84cac82b…`。
- 事实：两边各 432 局且全 `DONE`；baseline/candidate 同为 360-38-34、379 score points、score rate 0.877315。候选 mean margin +51.606，50 格改善、382 不变、0 退化；24-seed cluster bootstrap mean-delta 95% CI `[+6.28,+105.80]`，score-rate delta CI `[0,0]`。
- 目标层：50 个 step718 可卖库存命中格全部改善，mean +445.88、P10 +483、worst +5；但基线/候选均为 50-0-0，baseline failures=0，故失败减少门不可满足。
- 判决：总体计分严格提高与目标失败减少两门失败；按预注册停止，不进确认、不提交、不调阈值。结论只到“终局扫仓可因果提高现金/margin”，不能升级为“提高比赛得分”。
- 下一动作/停止：保留 public+hybrid 两槽。仅当新的辨识池在结果前固定镜像/强对手且确含基线平/负局时，才可作为新实验重检胜分翻转；不得从当前开发集事后挑样本。

### C-KAGG-010 — 149/140 局更新令 hybrid 在全部观察指标上领先（F）

- 权威来源：`kaggriculture/reports/remote_maturity_update_149_140_2026-09-09.json`；SHA-256 `6bd09ec91705c9e61ec249140eb2deb1b5e695ed1e7efbb3f8f01b0256a3cc1f`。只读同步，零 submission change、hidden seed/private opponent log。
- 事实：public 149 局 86-11-52、61.41%、rating 2272、mean 6,931.11、P10 −6,419.8、worst −35,237；hybrid 140 局 85-16-39、66.43%、rating 2554.4、mean 7,062.71、P10 −2,516.4、worst −20,432。hybrid-public 为 rating +282.4、score-rate +5.02pp、mean +131.60、P10 +3,903.4、worst +14,805。
- 更新边界：自 100 局门后 public 新增 16-5-27/rating −53，hybrid 新增 11-9-20/rating −29.8；两者新增计平局胜率均约 38.5%，成熟估计整体下移。live games 非配对，不能把 aggregate 差写成 causal union。
- 判决：纠正“public observed worst 更好”的旧叙述；hybrid 是全部观察指标更强的 active。仍保留两槽，因为官方 best-of-two hedge、public 策略不同且无新候选过本地门；不上传/替换/停用，只读监控。

### C-KAGG-011 — 155/144 局继续支持双槽冻结；两者成熟增量同步转弱（F/I）

- 权威来源：`kaggriculture/remote/summary_latest.json` SHA-256 `7046576ea5a41a6df92646c0de7af47eeb6524e99e6fbdaaa0f3d13a937cd368`；`reports/remote_failure_audit_155_144_2026-09-09.json` SHA-256 `7b5af91c9cf45989af75c2b3492d70cbd54838f0378773802f020a93adbb46aa`。只读下载 owned-seat replay/log；hidden seed、对手私有状态与未来 shops 未读，零 submission change。
- 最新读数：public 155 局 89-11-55、60.9677%、rating 2273.1、mean 6,350.26、P10 −7,753.8、worst −52,908；hybrid 144 局 87-16-41、65.9722%、rating 2552.5、mean 6,830.52、P10 −2,638.8、worst −20,432。hybrid-public 为 +279.4 rating、+5.0045pp、+480.26 mean、+5,115 P10、+32,476 worst。
- 成熟解释：相对各自 100 局门，public 新增 19-5-30/54、hybrid 13-9-22/44，计平局胜率分别约 39.81%/39.77%；二者同步转弱，不能把未配对 aggregate 差写成 hybrid 的因果胜率。failure audit 记录 public/hybrid losses 55/41、≤2,500 near-losses 25/26，且两者各有 5 局在 step718 public cash gap 非负仍输。
- 判决：hybrid 仍在全部 top-line 指标领先，public 仍是不同策略的第二槽 hedge。KG006 冻结、无新 candidate/confirmation；不从失败分层衍生 KG007、不调阈值、不上传/替换/停用。

### C-KAGG-012 — 官方引擎确认 reward 只取银行余额，终局清仓受前 10 单截断（F/I）

- 权威来源：本地固定 `kaggle-environments==1.32.7` 的 `kaggriculture.py` / `kaggriculture.json` / `README.md` / `AGENTS.md`，SHA-256 分别为 `bc8a54879ef02c7ea64b8b333d6a976f0ea65c4949149d01f463f23bccee653e` / `a82c89c1a2315b93f39775d8e025471a01b738647c9772658368ee6b1b6f4867` / `3081e52baf8eb2da5d861acc63a3636ce29425f6bdb79a67036ba234ac4ade00` / `e1a80501a7b02a212eaac9370ada4129a64e0ee6cb3cbc790f3d77d22863fe22`；与 Kaggle 官方公开仓库逐项核对。
- 引擎事实：默认 720 turns；胜者是季末 bank coins 较多者，未售 inventory 不计。最终有效周期按 unit actions→market→town consume→day refresh→DONE 执行，随后 `reward=float(farm.money)`。每方 market 队列只取 `q[:maxMarketOrdersPerTurn]`，默认前 10 单；后续单静默丢弃，前 10 单仍按原顺序处理。
- 对 KG-006 的含义：它在 432×2 中把 margin 平均提高 51.606，却没有改变 360-38-34 或 379 points；官方 objective 因而加强而非推翻原停止判决。不能把现金改善升级为比赛得分改善，也不能用未核订单位置解释/挽救既有零 W/T/L delta。
- 未来唯一可辨识动作：只在结果前固定、确含 baseline tie/loss 的镜像/强对手池重检；冻结原 market 顺序与插入规则，并逐格输出 `order_slots_before`、每个清仓单 index、accepted sell quantity/value、dropped-order count、最终 W/T/L。任一清仓单落到第 11 项以后、first diff 不符、合法性异常或 W/T/L 无翻转即停；不从当前 50 个全胜命中格事后挑样本，不生成候选或提交。

### C-KAGG-013 — 项目线 research scope 已封存，动态监控推进到 157/146（F/I）

- 封存收据：`campaign_completion_audit_2026-09-09.json` SHA-256 `a99294212ef26a3a40f41707901215acc2115a4888a29ae92e75f8bfe1ff405b`。它逐项确认成熟门、失败路径复盘、KG002/004/005/006 配对保护门、零未过门提交、双槽 rollback 与隐私边界；`campaign_research=closed`，剩余只读 heartbeat。该收据的 cutoff 为 155/144，不能当最新动态数字。
- 最新动态：`remote/summary_latest.json` SHA `756db35945d7ffcf1ea7e3acd6682d7f57bab24ee6f1ef078f7593dc5cfcb053`；maturity/failure receipt SHA `70b2a9b4b6a645b2a229cfcf06ca17e5fbc6e0157d1685658aa3c0ab90211498` / `99f1cecefabd88f687496883f0126b9c3c26971a157e4d429664b1c874ea16fc`。public 157 局 90-11-56、rating2273.6、60.83%、P10−8,215.8、worst−52,908；hybrid 146 局 88-16-42、rating2554.5、65.75%、P10−2,822、worst−20,432。
- 增量/判决：相对 155/144，两者都新增 1-0-1；hybrid 仍领先 rating 280.9、score-rate 4.93pp、P10 5,393.8 和 worst 32,476。样本非配对，零 candidate/confirmation/submission/slot change；继续 public+hybrid 双槽冻结，不因 heartbeat 重开实验。

### C-POKER-005 — E005 主 AP 上涨但域稳定性灾难失败（N）

- 本地来源：`poker/EXPERIMENT_LEDGER.md`、`poker/work/E005_exposure_validation.json`；判决：严格失败、不提交、停止 exposure-normalization 家族。
- 干预：仅移除 unlabeled/evaluation KS ≥0.075 的 `__max` 与 time-bin 特征；开发集 `shared_hands_calc` 乘 2/3；`dominant_flow_bb` 改为每 100 shared hands。E001 的其余特征、learner、标签、随机种子与 whole-pool folds 全部不变。
- 结果：95→63 features；confirmed Pair AP +0.002633、worst fold +0.002232、P95 +0.008065，`|Spearman|=0.082221`。但 score KS 从 0.061287→0.168920，fraction reduction=-175.62%，与预注册至少 +30% 相反。
- 结论：次级正向不能覆盖主域稳定性门；E004/E005 已共同否定 rank/exposure normalization。停止该表征家族，不提交，不再调阈值。下一步仅允许原参数复现公开 PU notebook，先建立合规强锚点；`MI_proxy` 延后。

### C-POKER-006 — 公开 PU notebook 成功复现但不是 Pair 强锚点（F）

- 本地来源：`poker/EXPERIMENT_LEDGER.md`、`poker/work/public_pu_ranker_repro_report.json`；source notebook SHA-256 `58acf6069c61016d55583c1dcfc88c97aa936cd51623830257dd55a1dbbf67f0`。
- 复现边界：执行原 cells 0、2、3、29–32、34–37、39–40，仅三处本地路径替换。confirmed whole-pool Pair AP 0.934033（低于 E001 0.948387）；PU stress AP 0.493722 不是 truth。
- 其他读数：confirmed Behavior MAP 0.831020、Evidence OOF MAP@5 0.443468、positive-family accuracy 0.967742。112,540 pairs 与 562,700/562,700 evidence hands 全量覆盖且均为精确共享手；identifier features=0，24,000 unknown ground-truth 仍为空。
- 结论：保留为公开方法的合法参考锚点，不提交、不声明为自有方法。它只能生成“action-response 是否补足 E001”的单因素假设，不能整体替换 E001。

### C-POKER-007 — E007 隔离 partner/outsider interaction（F/I）

- 本地来源：`poker/EXPERIMENT_LEDGER.md` 的 E007 预注册；状态：同折训练中。
- 单一干预：在 E001 raw95 与 confirmed-only learner 上只增加 41 个交互聚合（12 类 hand interaction 的 mean/P95/top-five mean，加 5 个归一化响应率）；标签、参数、种子和 whole-pool folds 不变，不加入 E006 的 XGBoost、PU weight 或 evidence ranker。
- 预期指标/门：Pair AP delta≥-0.005、worst≥-0.02、P95 positive separation≥+0.01、score KS 最多恶化 0.02 absolute、`|Spearman(shared_hands)|≤0.10`。
- 成本/风险：中等一次 OOF；风险是 action aggregates 暗含 exposure/时间漂移或来源归属混淆。
- 停止：任一门失败即冻结 interaction family、不提交；全过也只进入 early/late stability。

### C-POKER-008 — E007 数值全门通过，但收据路径冲突待修（F/I）

- 本地来源：`poker/work/E007_interaction_validation.json` 与项目线文件审计；状态：PROVISIONAL，不晋级。
- 暂定结果：Pair AP 0.948387→0.958898（+0.010512）、worst fold +0.016993、P95 separation +0.021505；score KS absolute delta +0.010646≤0.02，`|Spearman|=0.096058≤0.10`，unknown ground-truth labels assigned=0，数值上全过预注册门。
- 收据缺陷：原 validation 同时把 evaluation feature 与 evaluation score 指向 `E007_interaction_evaluation.parquet`，score 覆盖了 feature 文件。项目线已分离重建为 `*_features_evaluation.parquet` 与 `*_scores_evaluation.parquet`，但旧 validation 仍引用冲突路径/哈希。
- 最小验证：重写 validation 为两个独立 artifact/schema/row count/hash，并验证同一模型指标逐值复现；此前不进入 early/late stability、不提交。
- 成本/风险/停止：低成本收据修复；若任一哈希、schema、行数或指标不一致，E007 重新视为未验证/失败，禁止用暂定数值晋级。

### C-POKER-009 — E007 收据修复后正式过门；E007b 只测时间迁移（F/I）

- 权威来源：`poker/EXPERIMENT_LEDGER.md`、修复后的 `poker/work/E007_interaction_validation.json`。
- 修复事实：development features、evaluation features、evaluation scores 已分到独立路径，SHA-256 分别为 `9b3f718d...`、`d0738a1e...`、`12aa0f5b...`；JSON 路径/hashes 已纠正，主指标逐值不变。因此 E007 主 gate 正式 PASS，但仍不提交。
- E007b 前置：1,860 confirmed pairs 中 10 对只在前半或后半出现，原全量双向迁移断言在建模前中止，无模型结果。这里记录的“改为交集”是中间计划；最终方法由 C-POKER-010 取代，保留全部 1,860 pairs 并对缺失半段使用零 gameplay 特征。
- 最小实验：移除 phase-progress、quartile-bin、temporal-range 字段；同 whole-pool folds 比较 raw 与 raw+interaction 的 early→late、late→early。
- 门/停止：双向 delta≥-0.005、worst fold transfer≥-0.03、worst cross-time AP≥0.90、方向 gap≤0.05；排除集显著富集或任一门失败即撤销 E007 promotion。通过也只进入 Behavior/Evidence 与 packaging 审计。

### C-POKER-010 — E007b 有一致正增量但未达绝对迁移门（F/N）

- 权威来源：`poker/work/E007_time_stability.json`、`poker/EXPERIMENT_LEDGER.md`。
- 事实：early→late AP 0.823499→0.852369（+0.028871），late→early 0.825570→0.863528（+0.037958）；worst-fold transfer delta +0.005628，方向 gap 0.011158。所有相对门均通过，但 worst interaction cross-time AP 0.852369 < 0.90，故总 gate=false。
- 覆盖边界：保留全部 1,860 confirmed pairs；10 个单半段缺失 pair 以零 gameplay 特征进入，pool 边界由全阶段表补齐，held-out pool 不共享；unknown pair 未被作负例。OOF SHA-256 `eb20d9cb...`。
- 判决：撤销 E007 promotion，不生成候选、不与 PU 堆叠。41 个 interaction 仅保留为“真实正信号但绝对稳定性不足”的研究证据。
- 下一最小动作/停止：只读分层 E007b OOF；仅当非 ID/时间/exposure 的残差族在两个方向及至少四折同向，才预注册不同方法族。否则停止本地结构微调。

### C-POKER-011 — E008 outcome-conditioned marginal impact 仅单向过时间门（F/N）

- 权威来源：`poker/work/E008_marginal_impact_validation.json`；JSON SHA-256 `7ce5f56916f33eca81293af4541751247caff4872e9b84c1ff3814f480e58ade`，labelled/time OOF SHA-256 `f1a71adc…` / `983d9678…`。
- 单一干预：在 E001 raw95 上只加一个 `marginal_impact` scalar；它把 responder 的公开 realized net BB 相对 aggressor leave-one-responder-out 均值做 winsorized residual，以 `edge_count+10` 收缩后双向求和。E007 的 41 个 interaction 未进入；whole-pool folds、learner/seeds 不变，24,000 unknown 的 ground-truth labels assigned=0。
- 同分布结果：confirmed Pair AP 0.948387→0.948759（+0.000373），worst fold +0.003156；positive-above-unlabeled-P95 rate +0.005376；unlabeled↔evaluation KS 0.065096→0.064641（改善 0.000454）；evaluation score/shared-hands `|Spearman|=0.083209`。这些门均通过。
- 时间反证：early→late AP 0.823499→0.823214（−0.000284，要求 ≥+0.01）失败；late→early 0.825570→0.836116（+0.010547）刚过。worst time-fold delta −0.012156 与 direction gap 0.012902 均过，但总 gate=false。
- 结论：outcome-conditioned scalar 有方向非对称且效应接近零；E008 不晋级、不提交、不调 shrink/winsor、不与 PU 堆叠。
- 下一动作/停止：先只读审计 raw95 的双向 drift 与行为族支持；只有跨两方向、至少四折且非 shared-hands/exposure 的机制才立 E009，并直接复用严格时间门。无重复机制或任一方向 delta<+0.01 即停。

### C-POKER-012 — E009 将公开 conditional-information 思路落成严格时序特征（F/I）

- 权威来源：`poker/EXPERIMENT_LEDGER.md` 的 E009 preregistration；当前只生成 full/evaluation/early/late influence artifacts，尚无模型结果。
- 单一特征：same-street adjacent ordered-action transitions，influencer action 必须早于 target；动作折为 fold/check/call/small/large aggression，条件 state 只含 street、active-player bucket 与 target 动作前 to-call/BB bucket。折内 empirical directed CMI 乘 `n/(n+50)`，再减目标玩家受到的 max outsider influence；pair feature 只取 `min(net_A→B, net_B→A)`。
- 合规：full/evaluation/early/late 独立重算；不使用 result、cards、ID format、row order、label 或 future action；unknown 保持 latent。E001 raw learner/seeds/whole-pool folds 不变，不混 E007/E008/PU/behavior/evidence。
- 预注册门：feature `|Spearman(shared-hands)|≤0.20`；model confirmed AP delta≥+0.003、worst fold≥−0.02、P95 rate≥+0.005、KS deterioration≤0.02、model `|Spearman|≤0.10`、双向 time delta≥+0.01、worst time-fold≥−0.02、worst CMI cross-time AP≥0.84、gap≤0.05。
- 成本/风险/停止：中等 matched OOF；稀疏 state、时序错位、outsider support 与 exposure 混杂。任一门失败即归档 exact feature，不提交、不调 threshold/shrink。

### C-POKER-013 — E009 同时失败于主 AP、双向时间增益与最差迁移（F/N）

- 权威来源：`poker/work/E009_influence_validation.json`；JSON SHA-256 `2dc72e4d5eaf5870d57cd5a29548c712a5ac938c063a4193d35dd1c004a89b94`。
- 关键失败：confirmed Pair AP delta `−0.000811`（门 `≥+0.003`）；early→late `−0.003672`、late→early `+0.001823`（两门均要求 `≥+0.01`）；worst influence-transfer AP `0.819826`（门 `≥0.84`）。因此总 gate=false。
- 保护项：worst fold delta `−0.000447`、P95 rate `+0.005376`、KS absolute delta `−0.003346`、feature/model `|Spearman|=0.164300/0.083633`、worst time-fold `−0.010907`、direction gap `0.007566` 均过门；24,000 unknown 的 ground-truth labels assigned=0。这些不能覆盖四个关键失败。
- 判决：冻结 exact same-street conditional-information/influence 特征族，不提交、不调 `n/(n+50)`、state buckets 或 threshold，也不与 E007/E008/PU 堆叠。
- 下一动作/停止：停止当前局部结构特征搜索；只先做零模型的双向 label prevalence、table composition 与 action-schema drift 审计。没有跨两方向、至少四折且非 ID/时间/exposure 的训练时可见机制，就不立 E010。

### C-POKER-014 — E010 只换 confirmed-only 全局 pairwise objective（F/I）

- 权威来源：`poker/EXPERIMENT_LEDGER.md` 的 E010 preregistration；状态：已固定门，尚无结果。
- 前置审计：397 个含 confirmed labels 的 pool 中，152 全负、5 全正，只有 240 同时含正负类；逐 pool LambdaRank 会让大量可信监督没有 ranking gradient，因此用全部 confirmed pairs 作为一个 global query，同时继续按 whole-pool 划 held-out folds。
- 单一变更：E001 raw95 不变，只把 confirmed-only HistGradientBoosting classification 换成 deterministic LightGBM LambdaRank；冻结为 280 trees、learning rate 0.035、15 leaves、min child 12、L2 3.0、feature fraction 0.9，raw margin 只经固定 logistic sigmoid，不拟合 calibration。
- 合规：无 E007/E008/E009、PU、Behavior/Evidence、ID 或 row-order features；unknown target-latent，仅用于 stress；baseline 使用已有 E001 receipts，不重训。
- 门/停止：confirmed AP `≥+0.003`、worst fold `≥−0.02`、P95 `≥+0.005`、KS deterioration `≤0.02`、`|Spearman|≤0.10`、双向 time delta 各 `≥+0.01`、worst time-fold `≥−0.02`、worst pairwise cross-time AP `≥0.84`、gap `≤0.05`。任一失败即归档 global-pairwise objective，不调树/sigmoid/query；通过也不授权提交。

### C-POKER-015 — E010 全局 LambdaRank 在所有主门上灾难性失败（F/N）

- 权威来源：`poker/work/E010_pairwise_validation.json`；JSON SHA-256 `4504d433d83ce2f6359c4971c88a3d9d8ce105c2d4d1ea322265c09b31ed7177`。
- 事实：confirmed AP 0.948387→0.699491（`−0.248896`），worst fold `−0.189394`，P95 rate `−0.319892`；unlabeled/evaluation KS 0.065096→0.524167（`+0.459071`），`|Spearman|=0.120867`。
- 时间反证：early→late `−0.181126`、late→early `−0.254473`，worst transfer AP 0.571096、worst time-fold `−0.273549`、direction gap 0.071276；所有主质量/域/时间门均失败。24,000 unknown labels assigned=0，四个 artifact hashes 与 receipt 一致。
- 判决：single-global-query LambdaRank 破坏本题所需的分类/校准结构；冻结 pairwise-objective family，不调 query/tree/sigmoid，不提交。

### C-POKER-016 — E011 nested trusted hard-negative weighting 先过 Stage A 才测时间（F/I）

- 权威来源：`poker/EXPERIMENT_LEDGER.md` 的 E011 preregistration；状态：已固定，尚无结果。
- 单一变更：E001 raw95、confirmed-only HistGradientBoosting、seeds 与 whole-pool outer folds 不变；每个 outer fold 内先用其 confirmed training pools 拟合 pilot E001，只在 confirmed non-target training rows 中取 pilot probability 最高四分位为 hard set。final weights：hard negative 2.5、easy negative 0.5、positive 1.0，平均负类总权重约保持 1。
- 合规：global OOF score 不参与 mining；unknown 不进入 pilot、threshold、weight 或 final fit；无 PU、E007–E009、Behavior/Evidence 改动。
- 分阶段门：Stage A 先要求 confirmed AP `≥+0.003`、worst fold `≥−0.02`、P95 `≥+0.005`、KS deterioration `≤0.02`、`|Spearman|≤0.10`；失败则不做 time fits。通过后 early/late 各自在 outer-training half 内重算 hardness，并沿用双向 `≥+0.01`、worst time-fold `≥−0.02`、worst transfer AP `≥0.84`、gap `≤0.05`。任何失败即归档，不调 quartile/weights；通过也不授权提交。

### C-POKER-017 — E011 在 Stage A 三门失败，正确跳过时间拟合（F/N）

- 权威来源：`poker/work/E011_hard_negative_validation.json`；JSON SHA-256 `6202cc358ca5dfd45ba6f56552047dfe52c1768a9ff6e6bdb59d283dce2362d0`。
- 事实：confirmed AP 0.948387→0.945789，delta `−0.002598`（门 `≥+0.003`）；P95 rate delta `−0.005376`（门 `≥+0.005`）；evaluation `|Spearman|=0.117752`（门 `≤0.10`）。worst fold `−0.008371` 与 KS `+0.016531` 过保护线，但不能覆盖三项失败。
- 合规/成本：五折 hard set 均约 25.02%，负类总权重约保持原总量；unknown labels assigned=0。`passes=false`，`time_gate_status=not_run_stage_a_failed`，避免了无意义的双向 time fits。
- 判决：冻结 exact 75th-percentile、hard/easy weights 2.5/0.5 的 nested hard-negative scheme；不调 quartile/weights、不跑时间门、不提交。
- 下一动作/停止：E007b–E011 已连续失败。先只读汇总共同 residual/drift 与可用边界；没有与五个已冻族真正独立、且有双向/四折机制证据的新假设，就保持 E001、不立 E012。

### C-POKER-018 — E012 是 E001 后预先规划的独立 Elkan–Noto PU 试验（F/I）

- 权威来源：`poker/EXPERIMENT_LEDGER.md` 的 post-E001 stop-loss plan 与 E012 preregistration；`poker/work/E007_E011_failure_audit.json` SHA-256 `a82ce20e…`。状态：门已固定，尚无结果。
- 立项依据：E003 bagged PU 曾使 confirmed AP `+0.005981`、P95 `+0.013441`、P99 `+0.026882`，只因预注册 median-percentile 饱和而停止；原计划已要求将 bagged PU 与 Elkan–Noto 分开。E007–E011 audit 则显示各失败族 score delta 相关普遍很低，支持只测真正不同的 PU selection 方法，而不是旧特征调参。
- 方法/边界：raw95 与 sealed whole-pool outer folds 不变。临时 `s=1` 仅 confirmed targets，`s=0` 为 confirmed non-targets 加 target-latent unknown；confirmed rows weight 1，unknown 总权重等于 confirmed-negative 总数，indicator 不持久化。outer-training 内三分 stratified whole-pool split 估 `c=P(s=1|y=1)` 并 clip `[0.05,0.95]`；outer validation pools 不进入 c 或 selector fitting。
- 分阶段门：Stage A 要求 AP `≥−0.01`、worst fold `≥−0.03`、P95 `≥+0.01`、P99 `≥0`、KS deterioration `≤0.02`、`|Spearman|≤0.10`。失败即不跑 time fits；通过后才独立重建 early/late unknown features，要求双向 delta `≥0`、worst time-fold `≥−0.03`、worst transfer AP `≥0.82`、gap `≤0.05`。
- 风险/停止：SCAR 假设、c 估计/clip、unknown weighting 与 selection shift。任一门失败即归档，不调参、不提交；unknown 不得表述为 ground-truth negative。

### C-POKER-019 — 五实验残差综合把稳定瓶颈定位到 coordinated isolation（F/I）

- 权威来源：`poker/work/E007_E011_failure_audit.json`；SHA-256 `a82ce20e910b80f0cae883b59a36d2cea0a79ccb01d82d635953e38c86e172f1`。
- 事实：raw family AP 为 isolation 0.716667、directed 0.919071、soft 0.977378。E007 是唯一同时提高 full Pair AP 与双向 time 的候选：isolation full 0.804722，early→late 0.462772→0.572214，late→early 0.322589→0.497086；总体双向 +0.028871/+0.037958。它修复 4,553 inversions、新增 2,964，净去除 1,589；240 mixed pools 中 9 win/4 loss/227 tie。
- 反证：E008 仅净去除 320 inversions；E009/E010/E011 分别净新增 31/80,303/1,712。E007 与 E008/E009 score-delta Spearman 仅 0.1708/0.0954，说明并非数值复制，但都未把 isolation 的绝对时间 AP 提到门槛。
- 下一提案/停止：只审阅 behavior-conditioned risk target：directed/soft heads 保持 raw E001，E007 interactions 只给 isolation head；必须解决 evaluation 时 family 未知的无循环路由，并完整预注册后才可执行。当前不立 E013。

### C-POKER-020 — E012 Stage A 数值过门，但 faithful-Elkan–Noto 边界失败（F/N）

- 权威来源：`poker/work/E012_elkan_noto_validation.json`，SHA-256 `cac16b65b0f3aa19b3ae6768448c2653f00439c0c441e87f6c1002f384c5f9d4`；`poker/work/E012_methodology_audit.json`，更正引文元数据后的 SHA-256 `d41d45256bacea4be9c78ebfebbe6582034c904b1882f22f11f6d126b8667ba5`；外部原方法见 E-POKER-005。该更正不改变任何数值、方法边界或停止决定。
- 原门数值：confirmed AP `+0.009996`、worst fold `+0.002138`、P95 `+0.016129`、P99 `+0.064516`、KS `−0.029483`（改善）、`|Spearman|=0.033481`，Stage A numerical gate=true，unknown labels assigned=0。
- 方法失配：c 来自 inner 两折模型，outer/evaluation score 来自 full-refit 的另一个 g；24,000 unknown 总权重又被压到 confirmed-negative 数，改变自然 P∪U selector 基率。五折 outer-validation clip-to-one 比例为 10.78%–15.55%，labelled overall 13.49%，对比 evaluation 0.2586%/unknown 0.2083%；251/1,860 labelled scores 精确等于 1，unique 仅 1,610/1,860=86.56%，显示 g/c 尺度失配和大量 rank ties。
- 判决：overall `passes=false`、`time_gate_status=required_not_run`；停止在时间阶段前。只保留为 unknown-aware selector 开发信号，标 `PROVISIONAL_METHOD_MISMATCH`，不得称 faithful Elkan–Noto、一致概率或晋级证据，不提交、不对同一 E012 事后修法。
- future correction：必须新 ID，在任何结果前固定 same-`g_k/c_k` 三折 rotation 或可验证的 case-control/逆采样权重，并加 c-boundary、g>c/clip≤0.5%、unique≥99.5% 守卫；本轮禁止自动 E013。

### C-POKER-021 — B001 证明行为路由可测，但存在时间漂移与 ID 并列增益（F/I）

- 权威来源：`poker/work/B001_behavior_audit.json`，加固守卫后的 SHA-256 `02e7e03e217cdf403d120e938461482228d1e5cbfc55d24f751f7dae295fecf6`；implementation SHA `4cae28db…`，OOF/time artifact SHA 为 `71d7ce45…` / `4f85a92a…`。守卫更新未重跑模型、未改变数值。它不是 E013、pair-risk 候选或提交授权。
- 冻结边界：pair risk 精确复用 E001 raw OOF；三类 family learner 只在 372 个 confirmed targets 上训练，confirmed non-targets 不获 family label，unknown 完全不进入训练、验证、门或指标，evaluation 不打分，E007 interaction 不进入模型。
- 验证设计：沿用 E007 的五个 sealed whole-pool folds与 95 个 gameplay-only raw fields；报告 accuracy、macro/per-family recall、confusion、multiclass log loss/Brier，并在固定 active fractions `0.5/1/2/4/5/10/20/100%` 报 family AP 与 Behavior MAP。
- 关键防伪：官方 scorer 会把未激活 family 的 pair 全置零，再用 `pair_id` 字典序打破并列；ID 不能作为信号。因此每一档必须同时报告 exact official-order、seed 9917 的 512 次 random-tie 期望及解析 best/worst bounds；只有 random-tie 视图可解释模型质量。
- 结果：全期 positive-family accuracy/macro recall `0.943548/0.938447`；isolation/directed/soft recall `0.891304/0.939189/0.984848`。early→late 为 `0.852151/0.847081`，late→early `0.879032/0.869046`；isolation recall `0.804348/0.782609`，可测但最弱。
- 并列诊断：4% random-tie MAP `0.262344/0.261408/0.259238`（full/双向），official-order `0.274939/0.274252/0.265873`，后者虚增 `0.012595/0.012844/0.006635`；100% random-tie 则从 full 0.854915 降到双向 0.689634/0.679294，显示时间漂移。
- 完整性与停止：独立核验 1,860 OOF+1,860 time rows、risk exact、probability simplex、五折与 artifact hashes 全过；消费 time receipt 前强制 SHA=`eb20d9cb…` 且 full/time pair-fold assignments 完全相等。confirmed labels 覆盖 397/400 gameplay pools，3 个 label-empty pools 无直接行为验证；unknown used/labels=0、evaluation=false。B001 只通过“另行评审”前置条件，未证明 pair-risk/evaluation 提升；不能自动触发 E013、risk fitting、evidence reconstruction 或 submission，未来门必须以 random-tie 为准并单列 isolation 双向 stop。

### C-POKER-022 — 公开方法刷新没有新增 notebook 家族（F/N）

- 权威来源：`poker/work/public_research_inventory_2026-09-09.json`，SHA-256 `9b3adde347c213462ad30f22c72b904c5fafee78ff0d5394b4100289e1920401`；2026-09-09 16:46 CST 的 Kaggle public kernel inventory 返回 3 项。
- 覆盖：官方 metric、官方 getting-started、Nomannic PU-aware evidence ranker 均已本地保存并有哈希；workspace 中 Ravaghi/Nihilistic 文件属于另一个 wellbore-geology 比赛，已排除。新 public notebook 数=0。
- 可复用/不可复用：可复用的是同一 outer fold、cross-fitted predicted-family routing。不能把 public ranker 当 owned candidate，因为它捆绑 XGBoost/biased PU/大特征集，在同一 OOF grid 选 behavior rate、用 sklearn grouped-tie AP，并在外层 validation 选 evidence tree count；本地复现没有远端提交/分数。
- 判决：没有新方法族可自动启动；公开刷新只收窄搜索。若后续做 evidence，必须 owned nested validation、inner-only 选树、冻结 per-hand receipts，另行评审后才可执行。

### C-POKER-023 — EV000 v2 修复当前绑定，并量化 evidence/tie 薄点（F/I）

- 当前权威绑定：`EV000_independent_audit_v2.json` 状态 `PASS_CURRENT_BINDING`，SHA-256 `85adea3bc23ac6f6c25bd15cd2ce70135a383aeee2530d222a04836e9eea09fc`；它绑定 implementation `7518ed8731fa128cf66abee99dc95dc639673dfd0c025735ad4bdb028e09a49d`、feasibility report `27a8245e99419fce163e5d90843cd2585a1273a467d7841433dea732384a4726` 和另存的 `EVP-DRAFT-02` `a689703b2f3fc69cc054000f040b43cca80cee6bc4051feb62f8bd5d30810054`。
- 漂移修复：旧 audit 仍以 `PROVISIONAL_HASH_MISMATCH`/SHA `e5d8293a…` 留档，历史 PASS 单独保存为 `eeb72462…`；原 draft-v1 已恢复为 `7a170fd0…`。这保留了错误链而未覆盖历史，且 current v2 从 11 个 source hashes 重做了 372 targets、1,817 legal evidence hands、45,129 rows、20 features、30 outer/90 nested time cells与 tie structure。
- 支持量：full/early/late pairwise preferences 为 212,888/82,266/42,763。early 347 个 evidence-bearing query 中只有 346 个 trainable；outer fold 3 有一个 directed zero-preference query，必须原样保留。三家族最小 inner-training count=48，cross-time 最小 source/valid 为 early→late 68/7、late→early 35/15；late-isolation 五折仅 7/11/12/10/7 pairs、17/36/28/24/18 evidence。
- 并列门：random-tie AP@5 closed form 与 55 个枚举合成例完全一致。H0 的 full/双向 exact tie blocks 为 4,522/2,580/2,635，跨 rank5 为 65/70/70；当前 `started_at` 可完全解析，未来若同时间戳仍并列必须 stop，不可回退 ID/行序。这些是结构计数，不是 MAP 结果。
- 边界/下一步：model_fit/performance_view/evaluation/submission 均 false；`EVP-DRAFT-02` execution forbidden、没有 E-number。PASS 只证明 strict nested evidence validation 可实现；inner-valid 必须使用其余 inner folds 重训 B001 的 predicted family，禁止 true-family routing。没有另行监督批准不得运行。

### C-POKER-024 — pool 是唯一合法 bootstrap cluster，但 ordinary bootstrap 会产生空 family（F/I）

- 来源：`EVP_pool_provenance_audit.json` 状态 `PASS_COMPANION_ONLY`、SHA `eb11f4528c406d04b577aa254a3537cbe92cb080bf8e65a266153d95ab0b4545`；`EVP_bootstrap_support_audit.json` 状态 `REVIEW_REQUIRED_BOOTSTRAP_AMBIGUITY`、SHA `71b02ce03d923346a62ebb01e34ad606aa039c96a3d7ce53a4c26c0098e9092a`。二者均绑定 EV000 v2，未改绑定文件、未 fit/view/evaluate/submit。
- 依赖事实：45,129 candidate 与 1,817 evidence rows 在 pair-hand、两侧 player table、source hand 和 B001 receipt 五条 pool 来源全一致；372 queries 只占 245 `table_id` pools。183/54/8 pools 分别含 1/2/3 families，共 62 个跨-family pools；within-family multi-query pools 为 directed 25、soft 17、isolation 11，共 53。故必须按 `table_id` 聚类，不能独立抽 hands/queries，也不能分 family 抽样而丢失协方差。
- ordinary-bootstrap 反例：early→late outer fold0 的 7 isolation queries 只占 6/38 eligible pools，空 isolation 概率 `((38-6)/38)^38=0.00145855397`，5,000 次期望 7.293 个空 replicate；fold4 的 7/41 pools 期望 2.320 个。独立重算与 receipt 一致；full/反向概率虽小但仍非零。
- 方法缺口：v2 未冻结空格时 reject、omit、zero-fill 或改用别的抽样律；看到分数后任选会使 family/macro interval 无效。因此当前 `DO_NOT_IMPLEMENT_OR_EXECUTE`，不能用“丢空 replicate”补救。
- 待审最小 amendment：5,000 次 paired Bayesian cluster bootstrap；每 outer-fold/view 的 eligible `table_id` 取 seed 12673 的 `Exp(1)` 正权重，继承给 pool 内全部 queries，同一次 draw 共享 H0/L0/L1 与所有 families，以保留 pool 依赖且避免空 support。必须在执行前精确定义 weighted overall/family/macro/paired-delta aggregation；批准 amendment 也不等于批准模型、evaluation 或 submission。

### C-POKER-025 — v2 方法资格已撤销，v3 仅达到可监督评审的静态完备度（F/I）

- 撤销收据：`EVP_v2_methodology_withdrawal.json` SHA `98b1cea1bc56394eb1b801091dd269c9250857b524a65867b66d3667276e0804`，状态 `SUPERSEDED_REVIEW_REQUIRED`。v2 文件与 hash-binding PASS 均保留为历史事实，但 undefined empty-family bootstrap 影响 frozen gate，故 execution status withdrawn。
- 结构可行性：`EVP_bayesian_bootstrap_feasibility_audit.json` SHA `7a89801e9e5bd1bbd46bfb270bdbed04e06d525f3ce18f581254b4a7d1772849`，状态 `PASS_PROPOSAL_ONLY`。5,000 draws、seed12673、`SeedSequence([12673,view_index,outer_fold])`、eligible pool 的 `Exp(1)` 权重/折内 mean-one normalization；45 个 view/fold/family denominator 全正，最小为 early→late fold0 isolation 的 1.0232903，weight-stream SHA `c833ac7d…`。
- v3：`EVIDENCE_ONLY_VALIDATION_PREREG_DRAFT_V3.md` SHA `9464378b8406586367cbf3e26af708e5cf2573dccf03cb4bacd1f1a61276c045`；static audit `PASS_DRAFT_ONLY_AWAITING_SUPERVISION`，SHA `cfe4f8daddf25b81a5b8fe82c76ba30be8733e6ed33d01454cc3ba3e73dbc790`。它冻结 pool equality-key 只作复现枚举、同权重共享三方法/三 family、weighted query/macro、linear q05/q95、禁止 reject/omit/zero-fill，并保留所有 routing/tie/thin-cell stops。
- 边界/下一步：implementation/model/performance/evaluation/submission 均 false，无 E-number。结合 E-POKER-006，监督评审应先把区间明确标为 Bayesian cluster-weight sensitivity interval；除非另有结果前 coverage simulation，不得声称 frequentist confidence coverage。措辞未闭环或监督未批准即不实现。

### C-POKER-026 — v3 已关闭区间语义缺口，但仍未获得执行资格（F/I）

- 最新绑定：`EVIDENCE_ONLY_VALIDATION_PREREG_DRAFT_V3.md` SHA-256 `54776c546377da214626828f71deed383302ceee95142073da7b031a0d1723e5`；`EVP_prereg_v3_static_audit.json` SHA-256 `a45c55aae9cfac2b4caafb99511815b38b4da9c87c0b431edb985d554e117b91`，状态仍为 `PASS_DRAFT_ONLY_AWAITING_SUPERVISION`。旧 SHA `9464378b…` / `cfe4f8da…` 是修订前历史版本，不再是 current binding。
- 闭环事实：文档现在固定名称为 `90% paired Bayesian cluster-weight sensitivity interval`，声明 lower endpoint 仅是扰动鲁棒性门，不是 significance、posterior probability 或 coverage；任何输出若称 confidence interval、CI、credible interval 或 coverage interval，必须在查看 aggregate performance 前停止。static audit 明确 `frequentist_confidence_claimed=false`、`coverage_rate_validated_or_claimed=false`。
- 当时边界：5,000 draws、seed/RNG、同 pool 权重共享方法/family、weighted estimands、linear q05/q95、45 个正 denominator 和原 routing/tie/thin-cell stops 均未变；该 static-audit 快照中的 implementation/model fit/performance/evaluation/submission 全 false、无 E-number。协调源随后确认 `IMPLEMENTATION_ONLY_APPROVED` 已存在，因此“实现”这一项可改变；但 model fit/performance/evaluation/E-number/submission 与 result-bearing execution 仍未获批，静态 PASS 不能自授权运行。

### C-POKER-027 — v3 implementation-only 已诚实绑定为 present-but-unexecuted（F/I）

- 权威来源：`poker/work/EVP_implementation_containment_audit.json` SHA-256 `f04b10963b9e466cda2cb819a668344464c7efd7ead98ebb772b6879b1e5f75c`，状态 `PASS_IMPLEMENTATION_PRESENT_UNEXECUTED`；core/runner SHA `5871093ce9df04c7370db9c462fc85f77d15b8ebfb0e0dc65e65d7808c54005e` / `5a0f5aec85d2bad1ea852c4782200316a57704aa28edc8a99e7fb27b2c7a5fad`。
- 绑定事实：协调源授权范围仅为 source implementation + non-result static/synthetic tests；旧 prereg static audit `a45c55aa…` 未修改，其 `implementation_created=false` 明确只保留为历史。receipt 报告 core/runner 共 17/17、repository 23/23 tests、55 个 exhaustive random-tie cases 与 synthetic nested integration 通过；synthetic model fit=true，但 real model fit=false。
- 执行门：runner 在任何 competition-data path 打开前必须验证并一次性消费另行的 `RESULT_BEARING_EXECUTION_APPROVED` receipt；当前 implementation-only receipt 会被拒绝。未来 receipt 还必须精确绑定 draft、历史 static audit、core、runner 与本 containment receipt，且 rerun/evaluation/submission/E-number 都保持 false。
- 独立只读核对：receipt 内 core/runner/core-test/runner-test/static-script 五个 SHA 与当前文件逐一相符；`EVP_result_execution_consumed.json` 与 validation result/query/pairwise/model outputs 全部实际不存在。没有独立重跑模型或查看聚合性能。
- 当前决策：实现是可审工件，不是结果证据。下一步只剩监督对“一次 result-bearing development run”的明确 approve/reject；批准前保持 E001、无 E-number、无 candidate/submission。

### C-POKER-028 — v4 方法规范通过 72-cell 结构审计，但不构成执行许可（F/I）

- 权威来源：`poker/EVIDENCE_ONLY_VALIDATION_PREREG_DRAFT_V4.md` SHA-256 `3a9f20936f4173f72cb4ff867d296eb2945b43ca40cac0ee587b7fb4b83da22c`；`poker/work/EVP_v4_metric_coverage_contract.json` SHA-256 `4e821092161be0b0c80892af41ed61718e0a4930562b748a826da8a8bf9001e6`。独立判决 `PASS_METHOD_SPEC_ONLY`。
- containment：执行器自构造/解析固定的 v3 containment 路径并核对 SHA `f04b1096…`；authorization 路径在早期门禁前不解引用，替代路径会拒绝；未来 v4 receipt/hash 尚不存在且禁止猜测。
- C 选择：每个 outer fold/view 在 `[0.01,0.1,1,10]` 上汇总三个 inner folds 的 eligible-query、等权 query-mean exact random-tie AP@5；不用 family grouping、weight、macro、column 或 target，平手取更小 C。family 只在 score/top5 hashes 固定后连接。
- stages/coverage：Stage0 在任何 dev data 前且原子消费；Stage1 只做 full，Stage2 仅由 Stage1 PASS 开启，Stage3 仅由 Stage2 PASS 开启，失败终止且后续读取/哈希/工件缺席。3 views×(1 overall+3 family+5 folds+15 fold-family)=72 cells；query/candidate/evidence 在 family/fold/fold-family 三种汇总中均零不一致，below-floor=0。full floor=`(18,2058,90,14)`，time floor=`(7,458,17,6)`；两个 early→late isolation cells 恰为 7 queries，任一下降即触发 exact-tuple/floor stop。
- 边界/下一步：这是方法规范 PASS，不是实现/source correctness，更不是真实数据模型拟合、performance、evaluation、E-number、candidate 或 submission 授权。成本仅只读审计；风险是把完备规范当作运行证据。下一步若获范围授权，应先独立实现/source audit；result-bearing run 仍需单独明确批准。

### C-POKER-029 — v4 Stage 1 整文件 hash 违反 phase-only 延迟读取门（F/N）

- 权威来源：v4 draft SHA `3a9f2093…` 第 200–206 行明确 Stage 1 可读 full pair-hand columns 但排除 `phase_progress`，且不得 hash/open/inspect 该列；当前 runner SHA `4737f3c4…` 的 `FULL_STAGE_SOURCE_NAMES` 却包含 `development_pair_hands`，`_hash_stage_sources` 在 `_load_full_inputs_v4` 的 Stage 1 对整份 parquet 计算 SHA。
- 可证伪反例：同一 parquet 在 Stage 3 第 614–615 行才以 `columns=["pair_id","hand_id","phase_progress"]` 读取，证明整文件 bytes 包含阶段专属列。Stage 1 后续 `pd.read_parquet(columns=...)` 的列投影不能撤销此前整文件 hash。现有 containment SHA `f8a2e27b…` 声称 `phase_progress_read_in_stage_1=false`，但它是自生成实现收据，且 `poker/work/EVP_v4_source_audit.json` 不存在。
- 判决：`REJECT_SOURCE_AS_IS`；禁止真实数据/model/performance/evaluation/E-number/submission 运行。72-cell coverage 与 synthetic/repo tests 不覆盖 source-stage correctness。
- 最小修复/成本/风险/停止：只可在监督下修订方法合同，或在结果执行前另行冻结 Stage-1-only projected companion/content digest，再由独立 source audit 重验。成本低至中；风险是用 path/hash integrity 名义绕过 delayed access。source audit 未明确 PASS 或仍有整文件绑定即停止。向 Poker 任务的回灌因 workspace spend cap 未送达，不重试绕过。

### C-CUHK-001 — small20 全部命中过往 VLM 工件，只能作复现 smoke（F/N）

- 权威来源：`cuhk_x_large/reports/vlm_small20_frozen_protocol.json` SHA-256 `cfcc3ac2ef8dde83ff30b60a5a1119806dab1ae1e68ef4d0349adb461f52229b`；`cuhk_x_large/artifacts/manifests/vlm_small20_validation.csv` SHA-256 `c96d984b7af5bc8e712d951a8ac40dc1c247dfe7c1233520f4edff075e818041`。
- 设计优点：冻结先于 inference；20 个唯一 QA，10 subjects×2 rows，single/object 各 10；选择不看标签，父 OOF 是 subject-disjoint。
- 独立反例：排除当前 small20 输出后，20/20 selected `qa_id` 均已在更早 VLM 工件中出现，包括 zero-shot full122/object66，部分也在 multiview/mosaic/balanced/probe/8B。故判决为 `REJECT_AS_NEW_PERFORMANCE_OR_PROMOTION_EVIDENCE`，仅 `PASS_ONLY_AS_REPRODUCIBILITY/PIPELINE_SMOKE`。有效独立单位是 10 subjects，不是 20 rows；原协议只要求 task/half 内 positive net，未处理 subject-cluster uncertainty 或 multiplicity。
- 最小动作：当前 20 题只报告 exact repeat consistency、invalid rate 和管线完整性。新的 screen 必须在冻结时证明 qa_id+clip 与全部既有 VLM 工件零重叠；以 subject 为单位做 exact sign p≤0.05，并要求两个类别、两个固定 half 均为正。
- 成本/风险/停止：成本为新样本 provenance inventory 与最多 20 题的独立 screen；风险是样本量自欺、重复样本伪独立和多重切片择优。任一 subject 为负、implementation failures>1/20、历史重叠或无真正未见样本即停止。即使通过，只触发更大的 independent subject-disjoint validation，不直接晋级/提交。

### C-CUHK-002 — 真正 Fresh20 零重叠但 VLM 所有晋级门失败（F/N）

- 权威来源：Fresh20 report SHA-256 `f709b47a…`；final reproducibility manifest/verification SHA `f7d268a2…` / `a61f60ea…`；receipt recorded 2026-09-10T12:55Z。
- provenance：完整 HARn archive 1,956,322,919 bytes，CRC PASS；抽取 1,524 videos、524/524 training units、18 subjects。历史 inventory 先冻结，374 个 QA+clip 双零重叠 eligible rows；最终选 20 unique QA/clips、10 subjects、action/object 各一，selected overlap=0。
- 结果：20/20 valid、0 failures/retries；VLM 12/20=0.60，parent 13/20=0.65，net −1。action +3、object −4，halves +1/−2；subject 2 positive/3 negative/5 tied，one-sided exact sign p=0.8125。判决 `REJECT_AND_REFREEZE_VLM`，candidate NONE、submission prohibited/not performed。
- 最小动作/成本/风险/停止：零新增推理，冻结 `56122653` 与 `56108595` 两个 0.78070 finalists。风险是事后挑 action slice 或将 provenance PASS 当 performance PASS；任何基于 Fresh20 结果改门都停止。final freeze v3 验证 101/101 artifacts、16/16 model files、2/2 candidates。外部注册仍缺用户 contact email、affiliation、country/region、exact member names；2026-09-15 23:55 CST 前需用户填写并同意条款。

### C-BIOHUB-001 — 一轮 recovery OOF 有真实日志推进，当前只等待终态（F）

- 本地权威来源：`biohub_cell_tracking/official/oof_recovery_runtime_activity.json` SHA-256 `d20f76d183d8ef4e7436a4a7bf7c58c41de904a0db11909655239b2a0412d299`；`oof_recovery_kernel_status.json` SHA `86d63657bb0a1b096a66700af2eed8c12d18ed25793daeb49cebe3de3d9d106c`；ledger SHA `e00b759c…`。
- 事实：BH-0003、official run `348522481` 的本地落盘观察在 2026-09-09T13:36:01Z 显示 fold0/epoch1 batch1196/1454，latest log 仅落后 displayed runtime 6.4 秒，classification=`ACTIVE_PROGRESS`、status=`RUNNING`、output=0 B；这证明当时未卡死，但不是完成或性能证据。
- 动作/指标：仅由既有 hourly heartbeat 继续观察同一 run 的 terminal status 与允许的 artifact receipt；终态后才校验两方向 8 holdout movies、官方 metric、runtime、输出完整性与 frozen analyzer。成本为零新增计算。
- 风险/停止：禁止并行 rerun、取消或 competition submission；RUNNING/0 B 保持安静。只有 terminal COMPLETE/FAILED、工件校验失败或需要用户动作才升级；本轮研究任务未发起 authenticated Kaggle 查询。

### C-BIOHUB-002 — BH-0003 终态有效，但跨胚胎节点/边召回灾难性不足（F/N）

- 权威来源：finalization file SHA `aa7afd49…`（内绑 result receipt `a3548404…`）；validation/analysis SHA `6c62d8b2…` / `017da5bc…`。run `348522481` 已 COMPLETE，协议/下载工件/两折/日志校验全有效。
- 结果：16 holdout samples、runtime 13,491.46 s；fold 0/1=0.05588/0.01865，combined=0.03002，方向 gap 0.03723。edge Jaccard micro 0.02770、division Jaccard 0、node ratio mean −0.94983；missing edges 占 edge errors 99.596%。16/16 node-underprediction、16/16 edge-recall-limited、11/16 division-limited。
- 判决：`OOF_VALIDATED_DIAGNOSTIC` / `diagnostic_only_do_not_submit`。这不是 public baseline 0.944 的复现或替代证据；它把下一单变量定位为 detection-threshold downward calibration。
- 最小实验/成本/风险/停止：另获授权后仅在已下载 OOF 上预注册少量阈值下降网格，要求 combined、两方向下界、node/edge recall 同时改善，并守 FP/track fragmentation；成本低。任一方向不改善、division 仍 0 且 edge gain不足、或 FP/碎片化越线即停止此模型族，不再 recovery 训练或提交。

### C-TREEHSI-001 — per-class cap 10k 因 AA 退化被正确拒绝（F/N）

- 权威来源：`tree_species_hsi_2026/reports/oof_lightgbm_spatial_r1_cap10k_v4.json` SHA-256 `aa3377d4…`；commit `811c152`。
- 事实：相对 v3，仅 per-class cap 5,000→10,000；radius=1、160 estimators、152 features、connected-region 2 folds、seed 20260909 不变。OA 0.68814→0.69317（+0.00503），AA 0.62649→0.61906（−0.00743），fold OA/AA ranges 0.04122/0.01652。
- 判决/最小动作：违反 both-must-improve 预注册门，拒绝并冻结；未生成 test predictions、未提交。保留 v3 public 0.10387/rank31；下一步只能是独立方法族，在同折同时提高 OA/AA。
- 成本/风险/停止：当前零新增计算；风险是主 OA 小增掩盖 minority-class 退化。任何 AA 下降、单类 collapse 或只依赖约 7% public slice 的提升即停。

### C-HSI-001 — KaggleHub mount smoke 未证明数据可读（F/N）

- 权威来源：`hyperspectral_od_2026/runs/experiment_ledger.csv` SHA-256 `60e26ddd…`；`hsi26_data_mount_smoke_v2` 于 2026-09-10T03:07:53Z 结束为 `mount_smoke_failed`。
- 事实/边界：CPU-only smoke 终态 `CANCEL_ACKNOWLEDGED`，唯一有效日志停在 `Mounting files`；没有目录/list/image receipt，没有 GPU 训练或 submission。故这是数据访问基础设施失败，不是模型失败。
- 最小动作：另获授权后只做 5–10 分钟 CPU data-access preflight，验证官方 notebook 环境直接 competition dataset mount/path，固定最小 listing 与一图 hash；不下载全量、不建模。
- 成本/风险/停止：成本很低；风险是再耗 notebook quota、把 UI 提示误写成 mount 成功。限时内无路径/list/一图 hash 就停，禁止上传或训练等待中的 `hsi26_b5813_yolo11m_v1`。

### C-TARTAN-001 — E003 公开分与 CPU/offline 冷重放闭环（F）

- 权威来源：`tartan_imu/EXPERIMENT_LEDGER.csv`；release reproduction receipt SHA-256 `683f390e…`；输出 receipt SHA `c90b1c2b…`。
- 事实：E003 只将 E002 tree ceiling 600→1000，selected iteration 998，无 platform input/classifier/routing；submission `56117057` public 0.63142，官方 full-test 0.53485（lower is better）。CPU/offline 冷启动 117.42 秒、最大 RSS 723,648,512 bytes，30,644 行 SHA `4644bb8e…` 与原提交精确一致；official checkpoint/model SHA `ca8cc3e…` / `4cc94cf4…`。
- 推断/迁移：单变量、远端指标、资源预算与 exact replay 同时闭环，足以把 E003 作为可交付冻结候选；public/full-test 差异仍禁止推断私榜。其他项目可复用“先冷重放再晋级”的交付门。
- 成本/风险/停止：当前零新增计算；风险是 public chasing、平台路由污染和依赖漂移。新候选若不能在 CPU/offline 预算内 exact replay，或 full-test 方向不保留，立即回滚 E003。

### C-TRAFFIC-005 — onset top1/top2 无正向下界，Queue 冻结（N）

- 项目线回执：Task 1 density smoothing 的确认 delta 为 -0.0000155，已停止；此前 topology confirmation delta 为 -0.030723，复杂 queue trend/shockwave 也已停止。
- 实验来源：`traffic/artifacts/queue_onset_breadth_mini_v1/queue_onset_breadth_receipt.json`；只比较 onset 最终时间戳的 rank1/rank2/top2，ongoing、State、Physics、ODME 不变。
- 结果：development rank1/top2 为 0.311396/0.394730（-0.083333）；confirmation 为 0.495877/0.495877（0）；date-level 方向负或打平，且仅一 panel，不能提出 8-corridor 外推。
- 判决：没有正向 proxy 下界，不提交；保留 0.74210 off-by-one 锚点，Queue 无独立新证据不得重开。

### C-TRAFFIC-006 — Task 1 残差集中在拥堵切换尾部（F/I）

- 本地来源：`traffic/artifacts/task1_residual_audit_v1/task1_residual_audit_receipt.json`；只读审计，truth 仅作 evaluator/diagnostic，未生成候选。
- 事实：D12_I405_N 的 temporal-only 锚点覆盖 82,127 个目标 cells；确认块最大 speed/flow RMSE 分层均为 `congested_le60`，分别 6.9875 km/h 与 37.3478 vph/lane。总体均值偏差接近零，因此全局 bias/smoothing 不是下一假设。
- 推断/最小实验：先检查高残差时间是否在互斥日期重复对应可观测 congestion transition；若复现，只在开发集定义的事件 gate 内比较短时 persistence 与 temporal interpolation，其他 cells/组件不变。
- 指标/风险：总体及 congested `S_state`、逐日期/corridor、守恒残差；风险是 truth-peeking、单 panel 外推和 State/Physics 冲突。
- 停止：确认日期不复现，或候选确认不优于 temporal-only、任一 corridor 退化 >0.005、守恒恶化即停；`S_physics` 为 organizer-only unknown。

### C-TRAFFIC-007 — ODME λ=5 通过局部前沿门与全文件门（F/I）

- 权威来源：`traffic/artifacts/odme_lambda_frontier_v1_focused/odme_lambda_frontier_receipt.json`、`traffic/artifacts/odme_lambda5_v1/submission_validation.json`、`merged_diff.json`。
- 事实：λ=5 相对 λ=20 的 minimum split `S_link` gain +0.008185、minimum panel gain +0.001815、maximum prior-L1 ratio increase +0.030425，分别通过 +0.005、-0.01、+0.10 门；matrix-free λ=20 与 V32 原 NNLS 的相对 L1 仅约 4.3e-7。
- 包装：6,985,307 行、官方 key VALID、SHA-256 `c3aea84e...`；相对 0.74210 父文件恰有 70,708 行/单元变化，全部是 ODME `path_flow`，Queue/State/其他列不变。
- 边界：本地只可评分 `S_link`（Task 4 的 25%）；`S_od/S_dev/S_attr` unknown，所以“LOCAL_FRONTIER_CANDIDATE_EXISTS”不是总分提升。
- 最小验证/停止：若提交预算允许，单次隔离远端校准并预注册总分门；未过即回滚 0.74210、不继续扫 λ。禁止把远端单点解释为任一 organizer-only 子指标的因果证据。
- 远端状态：候选已作为 submission `56108199` 上传，状态 PENDING；提交前固定继续门为 public≥0.74410，否则回滚 `56107311` 并停止减小 λ。

### C-TRAFFIC-008 — λ=5 获得隔离远端正增益并成为新最佳（F）

- 权威来源：Kaggle submission 列表，2026-09-09 读取；submission `56108199` 状态 COMPLETE，public 0.74733。
- 事实：相对唯一父锚点 `56107311`/0.74210 增益 +0.00523，超过预注册 continue gate 0.74410 达 +0.00323；相对 V32 0.71846 累计 +0.02887。
- 归因边界：候选 SHA `c3aea84e...`，恰有 70,708 个 ODME `path_flow` cells 因 λ=20→5 改变，State/Queue 逐字节不变。因此可支持此单变量的总分增益，不能反推 `S_od/S_dev/S_attr` 各自方向。
- 下一最小动作：以 0.74733 为回滚点，只允许一个更小 λ 先跑全 10-panel×2-split、资源/prior/no-reversal 门；通过后才锁新的独立远端门。不得基于 LB 连续扫参。
- 停止：求解超预算/不收敛、任一 panel 反转、prior-distance 超门或远端未过预设增益，停止减小 λ并保留 0.74733。

### C-TRAFFIC-009 — λ<5 连续性确认失败，ODME 固定在 λ=5（F/N）

- 权威来源：`traffic/artifacts/odme_lambda1_vs5_failure_receipt.json`、`traffic/artifacts/odme_lambda2p5_vs5_smoke_d7_i10_e/odme_lambda_frontier_receipt.json`。
- λ=1：首个 D7_I10_E validation solve 在 tolerance/lsmr tolerance 1e-8、300 iterations 后仍未收敛；无 partial artifact，属于 FAILED_NUMERICAL_GATE，不是性能负证据。
- λ=2.5：同 panel validation/private 均可解，但相对 λ=5 的 minimum split `S_link` gain 仅 +0.001274，低于预注册 +0.005 扩展门；prior-L1 ratio 仅增 +0.003149，不足以挽救收益门。
- 判决：不扩 10 panels、不提交，λ=5/0.74733 固定为 ODME 锚点；停止减小 λ，不以放宽门槛追候选。

### C-TRAFFIC-010 — link-specific cutoff 保留覆盖但跨 panel 反转（F/N）

- 权威来源：`traffic/artifacts/task1_cutoff_residual_audit_smoke/task1_cutoff_residual_audit_receipt.json`；10 panels、development/confirmation 两个互斥日期块，只读 released-train truth，validation/private truth 未使用。
- 事实：`v_cut=0.60×released free_speed_kmh` 在各 panel 有 27–52 个唯一值且范围 5.58–13.62 km/h，非退化；>50% observability gate 后 minimum target coverage=1.0。
- 反证：minimum cutoff-minus-fixed residual-concentration lift=-1.781729，违反“任一 split/panel 不反转”硬门；top-1% tail share 最小差为 0 也无补偿证据。
- 判决：STOP_CUTOFF_GATED_FAMILY；不扩四周、不生成 event-gated candidate。公开物理流程只保留解释价值。
- 下一最小动作：转向不依赖固定 cutoff、只用输入期 innovation 的两状态稳健 Kalman/smoother，一 panel 互斥日期 smoke；confirmation 不优、任一日期退化>0.005、守恒恶化或使用目标 truth 即停。

### C-TRAFFIC-011 — 方向切换滤波在可观测性 preflight 即停止（F/N）

- 权威来源：`traffic/artifacts/task1_directional_observability_preflight_v1/task1_directional_observability_receipt.json`；receipt SHA-256 `1b78fb789b9a0f7a5f309ad0d6fb322b2fb50d0c95dd445bdb0b91ef0f7c78a9`。只读 released masked inputs、eligibility 与网络顺序/长度；未读 unmasked target truth，未生成预测。
- 预注册门：validation/private 的每个 panel×split 都必须满足 maximum adjacent spacing≤3 km、上游/下游 3 km 内观测覆盖各≥90%、双向≥80%、任一方向≥99%。
- 事实：20 个 panel×split 仅 10 个通过；worst spacing 7.771 km，最低 upstream/downstream/both/either 为 0.850683/0.848030/0.739499/0.959215。五个 corridor direction 在两个 split 均至少违反一项。
- 结论：外部文献给出的传播/可观测性前提在全赛域不成立；冻结 directional switching family，不实现 filter、不提交。不能把局部 10/20 通过事后改成 panel selector。

### C-TRAFFIC-012 — 首版 grouped temporal baseline 存在不可部署的月内 truth 依赖（N）

- 权威来源：`traffic/artifacts/experiment_ledger.csv` 对 `task1_grouped_temporal_baseline_v1` 的追认审计；原 receipt SHA-256 `01a5cded29d13df6f330650940df3a46ca38d9b1c4430f1ffe0ce18887fed616`。
- 事实：首版在 January/February full-month replay 得到 dev/confirm `S_state` 0.908699/0.911208、公开 `S_FD` 0.986222/0.986445，且 7,089,289 target cells 无缺失；但“exactly seven days earlier” fallback 会让月内后续 holdout 日使用同一封存月较早日的 truth。Kaggle validation/private 月不会逐日揭示这些标签，故状态为 `INVALID_DEPLOYMENT_MISMATCH`。
- 结论：数值可复现不等于可部署；该分数不得参与模型选择或作为候选基准。
- 下一动作/停止：只重建 pre-block frozen profile control，整月预测不得使用月内 target truth；先过时间可用性、全 panel/regime、schema/key/coverage 守卫。任何月内 truth dependency 或缺失 cell 即停，在合法 control 前不测试新 State family。

### C-TRAFFIC-013 — pre-block frozen V32 State control 已建立（F）

- 权威来源：`traffic/artifacts/task1_grouped_v32_frozen_profile_control_v1/task1_grouped_v32_control_receipt.json`，receipt SHA-256 `079c2bb7…`；anchor reproduction receipt SHA-256 `49222bdf…`。
- 信息边界：每个 panel 的 January/February profile 只用 holdout 前 214/245 天；same-day 只读 released masked values，target truth 仅在该日 prediction/profile 固定后打开。
- 事实：7,089,289 target cells、0 missing、60 panel-regime 全覆盖；dev/confirm `S_state` 0.908792/0.911292，公开 `S_FD` 0.986250/0.986470，runtime 99.63 秒、peak 457.8 MB。`S_LWR/S_physics` 未知。
- 复现：D7_I10_E validation day 的 5,884 keys 与 archived V32 全匹配，speed 全匹配；仅 1 flow cell 相差 0.104587 vph，当前环境 rowwise V32 与新 matrix 实现精确匹配，该差仅为官方 600-vph normalizer 的 0.00256%。
- 结论：这是后续 State 单因素实验的唯一合法 control；首版 rolling-seven-day 数值永久保留为 INVALID。
- 下一动作/停止：只用 January development 按 prediction source/mask/history support 做残差归因，预注册唯一跨-panel 机制后在 February confirmation 一次打开；总体不优、任一 panel regression>0.005、FD/尾部恶化或 same-block truth dependency 即停。

### C-TRAFFIC-014 — historical profile 对 scored targets 实际零相关（F/N）

- 权威来源：`traffic/artifacts/task1_v32_source_coverage_audit_v1/task1_source_coverage_receipt.json`；receipt SHA-256 `c6c2afbc…`。只读 validation/private masks 与精确 V32 fallback 顺序，无 target truth、无预测。
- 事实：6,740,599 scored State targets 中 0 个依赖 historical profile；99.995253% 由 same-day temporal interpolation 完整覆盖，剩余仅 320 cells 走 spatial fallback。profile relevance share=0，低于预注册 0.001 门。
- 结论：robust historical-profile family 在当前数据流没有作用域，冻结且不拟合。后续改进必须针对 same-day temporal reconstruction 或另一个组件，不能再调 profile。

### C-TRAFFIC-015 — nearest-fill 不保留拥堵模式，线性插值在两月均胜（F/N）

- 权威来源：`traffic/artifacts/task1_temporal_mode_ablation_v1/task1_temporal_mode_receipt.json`；receipt SHA-256 `a5c6d53c…`。
- 单一干预：D7_I10_E 上仅改变 linear interpolation 与 12-slot 内 nearest visible observation 的 blend weight；January development 选权重，February confirmation 一次打开，profile 均 pre-block frozen，truth 仅在全部预测固定后作 evaluator。
- 事实：development 选择原 control weight=1.0，`S_state` 0.903327；pure-nearest 0.881731（−0.021596）。confirmation control 0.913191，pure-nearest 0.895664（−0.017527）；向 nearest 的移动单调变差，FD frontier 变化小于 0.00017。
- 结论：STOP_TEMPORAL_MODE_FAMILY；不扩全 panel、不提交、不调 blend。
- 下一动作/停止：若继续 State，只允许用 pre-block historical days 模拟官方 masks，训练低容量、非 ID 的 same-day nonlinear residual interpolator；先单 panel January/February，confirmation `S_state` 至少 +0.01、任何日不低于 −0.005、FD≥−0.001 才扩。否则保持 λ=5/0.74733 并停止 State 微调。

### C-TRAFFIC-016 — ongoing trend 只在 confirmation 后验变好，Queue 仍冻结（F/N）

- 权威来源：`traffic/artifacts/queue_ongoing_trend_ablation_v1/queue_ongoing_trend_receipt.json`；receipt SHA-256 `bcf58e37…`。
- 单一干预：保持已验证 onset 与 queued-now persistence 不变，只在 8 panels 的 ongoing nonqueued links 扫 `max_cross_step={0,2,3,4,5,6}`；released noisy eligible observation IoU 仅作 proxy，official `S_queue` 未知。
- 事实：development control 0.667678，steps2–4 同分、5–6略差，故选择 disabled control。confirmation 的 step3 为 0.528761 vs control 0.505043，但只有 2/8 panels 改善；按预注册不能从 confirmation 反选。正式 selected delta=0、changed rows=0、positive panels=0。
- 结论：开发未选非 control、跨 panel breadth 失败；冻结 ongoing-trend family，不候选化、不提交。confirmation-only 正信号保留为防后验选择反例。

### C-TRAFFIC-017 — nonlinear residual 两月正向但低于预注册扩展幅度（F/N）

- 权威来源：`traffic/artifacts/task1_nonlinear_residual_ablation_v1/task1_nonlinear_residual_receipt.json`；receipt SHA-256 `d1a69a29c712d27ed08495544fdc621c255cd3d877ec5ce6f17fbb9fbab368fa`。
- 信息边界：D7_I10_E；residual training labels 全来自发布的 `train/mainline_states`，January 是 February confirmation analog 前已发布 train，未使用 scored-split labels。features 只有 same-day 端点/斜率/距离、时段与公开 free-speed/capacity，无 link ID；January 只选 correction strength，February 不回调。
- 事实：development 选 strength 1.0，`S_state` 0.903327→0.907732；confirmation 0.913191→0.917719，delta `+0.004528`，低于固定 `+0.01` 扩展门。transition delta `+0.005370`、public FD `+0.001432`、worst-day `+0.002864`，629,335 target cells、0 missing；估算 State-only weighted total delta `+0.001585`，organizer `S_LWR/S_physics` unknown。
- 判决：稳定正向不能覆盖幅度门失败；`STOP_NONLINEAR_RESIDUAL_FAMILY`，不扩全 panel、不生成候选、不提交、不事后降低 +0.01。
- 下一动作/停止：本轮停止 State 微调，保持 λ=5/0.74733。先只读重排剩余组件的可观测误差、可控性与总分上界；无足够独立下界则不立新候选。

### C-TRAFFIC-018 — 组件机会审计找不到足以承担提交成本的新族（F/N）

- 权威来源：`traffic/artifacts/component_opportunity_audit_v1/component_opportunity_receipt.json`；SHA-256 `6481e142e8d9b3b9cbd24f6ca2294b936715c2431496527b13be117ed9df3e84`。0 prediction rows、未读 target truth/hidden labels。
- 门：固定总分成本下界 0.0035，等于 State `+0.01×0.35`。State 理论余量 0.031048 但近期单 panel 信号仅 0.001585、不是全 panel lower bound；FD 最大余量 0.000677；λ=5 的 `S_link` 即使满分最多贡献 0.000254。
- ODME 可辨识性：20 panel-splits 的 operator nullspace fraction 0.9444–0.9802、rank 35–100；大 organizer-only 权重是理论 upside，不是本地可证 lower bound。
- 判决：qualifying independent families=0，`HOLD_LAMBDA5_NO_NEW_EXPERIMENT_OR_SUBMISSION`。本轮独立重跑当前套件 31/31 tests 通过，submission ledger 仍 3 条。

### C-TRAFFIC-019 — 当前最佳全表 lineage 只含两项已验证改动（F）

- 权威来源：`traffic/artifacts/current_best_lineage_audit_v1/current_best_lineage_receipt.json`；SHA-256 `a6acab847ca80090b59655db688254ce426bca40ed55ad33cd9ea6b791421cba`。
- 事实：逐 cell 比较 6,985,307 行，只有 Queue 160 rows/cells（全部 `1.0→0`）和 ODME 70,708 `path_flow` rows/cells 变化；State 6,740,599 rows 零变化，无意外 task/column。官方 key/schema/domain 全复验 `VALID`，0 blank/nonfinite。
- 归因：Queue-only public +0.02364，ODME-only +0.00523，总增益 +0.02887；当前 submission `56108199`、0.74733、SHA `c3aea84e…`。
- 判决：`HOLD_CURRENT_BEST_NO_FURTHER_MICROTUNING`；只读维护 lineage/健康，不生成新预测或提交。

### C-TRAFFIC-020 — 显式冻结 solver 后，当前最佳可从公开输入逐字节重放（F）

- 权威来源：`traffic/config/current_best_freeze_v1.json` SHA `ddf2da9cf517bd392c5cee19e435ecf8db72544b9d4f63122cffc5b3bfca26eb`；`traffic/artifacts/current_best_full_replay_v1/current_best_full_replay_receipt.json` SHA `ca275b57863fc568be4121aa11375b615a64be110d5faa15dd3964232a581b3e`。
- 纠错：当前 ODME 脚本默认曾漂为 `tol=1e-8/lsmr_tol=1e-8/max_iter=300`，而 submission 56108199 实际回执为 `1e-9/1e-10/200`；现改为显式配置钉死，避免“同 λ 不同数值路径”。
- 重放：从固定 V32/public inputs 重算全部 20 个 ODME panel-splits、Queue 160 个 `1→0` cells 与 ODME 70,708 `path_flow` cells；最终 6,985,307 行 rebuilt/canonical SHA 均为 `c3aea84e5c62f873bad26178db9eddc5b69cf874cffa4f99009c056e698ef8fa`，byte-identical=true，153.91 秒、434.16 MB。
- 边界/判决：target truth、hidden Queue labels、boundary flows、hidden ODME metrics 均未用；`FREEZE_REPLAY_PATH_VALID`。新增加回归后独立复跑 33/33 tests 全过；这提高复现可靠性，不是新分数或新候选。

### C-TRAFFIC-021 — campaign v2 无 warning，但最终选择仍是时间边界（F/I）

- 权威来源：`traffic/artifacts/campaign_readiness_audit_v2/campaign_readiness_receipt.json` SHA `35776c2e626e4c66a04cd324b51aaa4547f5858e42b2db712045498f5278e2c9`；archive SHA 已现场复验为 `aa122173…`。
- 状态：`READY`，15 PASS、0 WARN、0 FAIL。v1 的唯一 WARN 已由单独 replay receipt 覆盖，原历史 ledger 空值未回填；不能把 current-machine replay 冒充原运行实测。
- 时间边界：当前 `RESEARCH_BEFORE_D30`，`goal_complete=false`；D30=2026-10-08 14:55、D3=2026-11-04 14:55、deadline=2026-11-07 14:55（CST）。下一动作是在 D30 重跑只读 readiness，D3 才允许最终候选选择检查。
- 停止：继续保持 56108199/0.74733；无 ≥0.0035 独立本地下界不重开实验或提交。readiness 是当前健康证明，不得表述为比赛目标已经完成。

### C-TRAFFIC-022 — 七个历史资源空值已用旁证重放闭环，而非伪造回填（F）

- 权威来源：`traffic/artifacts/legacy_resource_replay_v1/legacy_resource_replay_receipt.json` SHA `ae9eb30e42d6f968b322f0c214315dd411631bd842aa469db227c8c3105474a3`；backfill CSV SHA `32edf33d…`。
- 范围：覆盖 V32 anchor、Queue natural/merged、public release audit、current-best lineage 和 λ=1 numerical gate 的共 7 个缺失 runtime/peak-memory 字段；原账本单元保持空，旁证明确标为 current-machine deterministic replay。
- 结果：五个正常步骤均复现既有 SHA/结构；λ=1 以 exit 1 精确复现既定 numerical failure，无 output/candidate/score comparison，也未重开低 λ 家族。总 runtime 176.83 秒、peak 723.45 MB；hidden labels/target truth 未读。
- 判决：资源证据链完整后 readiness v2 升为 15/0/0；新测试加入后独立复跑 Traffic suite 34/34 通过。这是证据完整性提升，不是模型或榜分提升。

### C-TRAFFIC-023 — readiness v3 把 D3 控制纳入健康证明（F/I）

- 权威来源：`traffic/artifacts/campaign_readiness_audit_v3/campaign_readiness_receipt.json` SHA-256 `38e9e9874d6041855b37caf7a8b45f8be2000d8e4a5ed8c1862ade713f14250c`。
- 事实：截至 2026-09-09 18:20 CST，状态 `READY`、19 PASS/0 WARN/0 FAIL，阶段仍是 `RESEARCH_BEFORE_D30`、`goal_complete=false`；冻结配置、候选/rollback 文件哈希、27 条实验/3 次提交、10 panels/60 State groups/20 ODME panels、lineage/full replay、隐藏信息边界与 D3 控制均已入检查表。
- 边界：这是当前控制平面健康证明，不是最终候选选择、外部提交或战役完成。下一只读 checkpoint 仍为 2026-10-08 14:55 CST；无 ≥0.0035 独立本地下界，保持 56108199/0.74733。

### C-TRAFFIC-024 — final selector dry-run 能复现候选/回滚，但严格拒绝提前 final（F/I）

- 权威来源：`traffic/artifacts/final_submission_preview_v4/final_submission_selection_receipt.json` SHA-256 `6ddd42dc66ba28630d00add1a0d66a61060f2ae18d044b7c4b80c91da236275b`。
- 事实：`PREVIEW_READY_NOT_FINAL`、`dry_run=true`、`selection_final=false`。preview 选中既有 `56108199`/0.74733/SHA `c3aea84e…`，并保留 `56107311`/0.74210/SHA `7e5c790f…` rollback；lineage `VALID_FROZEN`、full replay byte-identical、readiness `READY`、late experiment violations=0，候选与证据哈希均现场重验。
- 时间/安全门：未执行 Kaggle 动作，`internal_selection_complete=false`、`campaign_goal_complete=false`。D3 前 non-dry 必须拒绝；D3 后也要使用观测年龄 ≤15 分钟、未来偏差 ≤60 秒的 fresh `READY_FOR_FINAL_SELECTION` receipt，并在选择后再跑 readiness。preview 不是 final。

### C-TRAFFIC-025 — lifecycle receipt 登记已幂等化，但没有提前激活未来阶段（F/I）

- 权威来源：`traffic/artifacts/lifecycle_evidence_registry_v1/lifecycle_evidence_registry_receipt.json` SHA-256 `ab5d1fc3625ee26b38adcc54f03b9c51ae1573b0d5982f4493e10572cedaa09d`；source SHA `8d272052…`，tests SHA `dd9943ad…`。
- 事实：14 个隔离用例通过 readiness 显式激活、final-selection 自动登记、重复登记幂等、单文件原子替换、registered receipt live-gate 校验及现有 receipt 路径不可覆盖；验证前后 live campaign status/experiment/submission ledger 三个哈希完全相同。当前全 Traffic suite 独立 46/46 通过。
- 信息边界：predictions unchanged、Kaggle action=false、hidden labels/organizer-only metrics 未读。`--activate` 仍受 live clock 的 15 分钟年龄/60 秒 future-skew 限制；pre-D3 preview 不会因 registry 存在而变成 final。
- 下一动作/停止：D30 用新的输出目录运行并显式激活 readiness；D3 依次激活 `READY_FOR_FINAL_SELECTION`、15 分钟内 non-dry internal selection、再激活 postselection `READY`。任何源/receipt/hash/时钟漂移都停在本地，不改预测、不对外提交。

### C-TRAFFIC-026 — 四任务 baseline 已由直接哈希合同而非账本文字证明（F）

- 权威来源：`traffic/artifacts/four_task_baseline_audit_v1/four_task_baseline_receipt.json` SHA-256 `58a0cc1da4c6bbeac57a8ed4b7187b2bfc2d5b3ca2413b2dc605bf6ecda5337c`；matrix SHA `5b1d109ea187454964deb9c86305357c3b264b0892fdf3df301c2244990915b0`；contract/source SHA `34f9d8a1…` / `a0a3d949…`；官方代码 commit `205faf1b…`。
- 直接覆盖：State 为 10 panels×3 regimes×2 holdouts=60 groups、7,089,289 target cells、0 missing，dev/confirm `S_state=0.908792/0.911292`；Queue 为 174,000 rows、8 eligible panels×2 splits 各 10 个 `1→0`，共 160；ODME λ=5 对 λ=20 为 10 panels×2 splits 全部 `S_link` 正增益、70,708 rows。
- 独立重放：新输出 matrix 与权威 matrix byte-identical；删除 `executed_at_utc/runtime_seconds/peak_memory_mb` 后 replay receipt 与权威 receipt 逐字段相同。完整 Traffic suite 52/52 PASS。
- 物理/隐藏边界：Physics 只记录 public triangular-FD `S_FD=0.986250/0.986470`；官方 `S_queue`、`S_LWR/S_physics`、`S_od/S_dev/S_attr` 仍为 null。`VALID` 只证明 D30 baseline/跨 corridor 证据完整，不是四任务官方成绩、新模型或提交。

### C-TRAFFIC-027 — readiness v5 纳入四任务合同，仍未提前完成 D30/D3（F/I）

- 权威来源：`traffic/artifacts/campaign_readiness_audit_v5/campaign_readiness_receipt.json` SHA-256 `ed45c04cb185b610af651b036ec4e7dbd17339aa0e0c35b425827e8475ebe61b`；checklist SHA `ae5075b6e39fcfdcd8025d7c2a7599ed6f7645c6ab1a14f7d45b5ab4127bdc1c`。
- 状态：21 PASS/0 WARN/0 FAIL，四任务 baseline、三次提交归因、当前/回滚工件、D14/D7、隐藏信息边界与 D3 preview 均进入检查表；实时 activation 年龄 10.93 秒，archive SHA 现场通过。
- 边界/下一步：phase 仍 `RESEARCH_BEFORE_D30`、`goal_complete=false`，下一 checkpoint 2026-10-08 14:55 CST。当前 activation 只登记今天的健康 receipt，不能替代 D30 新鲜重跑或 D3 final selection；无预测、Kaggle、hidden-metric 动作，保持 `56108199`/0.74733。

### C-TRAFFIC-028 — 当前执行环境已由 v3 精确版本与 capability receipt 锁定（F）

- 权威来源：`traffic/artifacts/runtime_environment_audit_v3/runtime_environment_receipt.json` SHA-256 `197b1d69fc7503b729a466625ca5bcc15a969e1d4cf39daa84b5fddf4ff6a7db`；capability matrix SHA `b409935fb1e6997fcab628963614a7c8181dd40c591e0bc10464aed08f3f7f4b`；contract/lock/source SHA `bba4f9ed…` / `a94b2be…` / `3e26b914…`。v1/v2 已因后续 lifecycle/system-manifest CLI 引起的 `run.py` 哈希漂移历史化。
- 事实：CPython 3.13.2、pip 26.1.2、10 个 direct/transitive 包、Darwin arm64 与 Accelerate BLAS/LAPACK 精确匹配；NumPy finite、Pandas/PyArrow roundtrip、SciPy NNLS、sklearn HGBR、psutil、11 个 CLI help 与完整 64-test suite 共 7 项 capability 全 PASS。临时新目录独立重跑同样 `VALID`、64 tests。
- 信息边界：competition data、submission artifact、hidden label/metric、external action 均 false。该收据只证明当前机器上的可执行依赖闭包，不证明跨平台 byte identity、任何 component score、候选增益或 submission。

### C-TRAFFIC-029 — readiness v8 消费 runtime v3、system manifest 与 lifecycle policy 后仍保持时间未完成状态（F/I）

- 权威来源：`traffic/artifacts/campaign_readiness_audit_v8/campaign_readiness_receipt.json` SHA-256 `e24b1e0a2fbb593399b45dec057c85f665409857ba3a0ca64ad9452f2f045038`；checklist SHA `8f9665afa6eab15d2458251038c7514941a4005f4360f460f076fe7638a72aee`。v6/v7 在后续控制面级联前保留为历史，不再是 current binding。
- 状态：24 PASS/0 WARN/0 FAIL，phase=`RESEARCH_BEFORE_D30`、`goal_complete=false`、archive hash verified，下一 checkpoint 仍为 2026-10-08 14:55 CST；runtime v3、system manifest 与 lifecycle-policy receipt 均已进入 live status 和检查表。
- 独立复核：使用相同 as-of、当前激活后状态与新输出目录再跑仍为 24/0/0；checklist 唯一文本差异是 activation 已把 v8 自己追加到账本，experiment rows 从 44 变 45，因此不声称 checklist byte-identical。
- 边界/停止：环境 READY 与 campaign READY 都不是官方四任务分数或 final selection；`S_queue/S_LWR/S_physics/S_od/S_dev/S_attr` 仍 null，无预测或 Kaggle 动作，无 ≥0.0035 独立本地下界时继续冻结 `56108199`/0.74733。

### C-TRAFFIC-030 — 生命周期名称现在由可执行策略而非文字承诺约束（F/I）

- 权威来源：`traffic/artifacts/lifecycle_policy_audit_v1/lifecycle_policy_receipt.json` SHA-256 `5af856f46b6318fc61ee16197f535add67b56c1d3667bb91fb92ad5c0ad40050`；policy/source SHA `5b574c05…` / `dd7ec735…`；matrix/deadline/violations SHA `e0163ce4…` / `617b7de2…` / `aeefc464…`。
- 事实：D30 四任务 baseline、D14 frozen lineage、D7 byte-identical replay 三份 receipt 的 deadline/hash/ledger status 全部重验；当前 post-freeze experiment/submission violations 均为 0。8 个合成 enforcement probes 证明 D14 拒绝新 tuning/新 submission，D7 只允许 reproduction/integrity，D3 只额外允许 documented bugfix/final selection，普通 model/submission 仍拒绝。
- 独立复核：完整 suite 58/58 PASS；同 as-of 新目录重跑三张输出 CSV 全部 byte-identical，receipt 除时间/资源字段外语义一致。
- 边界：测试的是本地策略分类与现有账本，不执行预测或 Kaggle 动作，也不自动完成未来阶段。真正到 D30/D14/D7/D3 仍需新鲜 live audit；phase 当前仍为 `RESEARCH_BEFORE_D30`。

### C-TRAFFIC-031 — system manifest 已把实现/证据闭包固定，但也触发控制面停止门（F/I）

- 权威来源：`traffic/artifacts/system_implementation_manifest_v1/system_implementation_manifest_receipt.json` SHA-256 `5b30c7a5cd9ef15d4cc788873d0394fad434ae068df7384d643e785061c5e7da`；manifest CSV SHA `b6c84afb8027c40f834cf9eef5ea35b4f7f4f13b0e63b225366ca8fbc626c52d`；contract SHA `b5954def21ed759a5249727867a0c7fd1dd1e3d35ffec9492d9095d3d0100e9c`。
- 事实：87 个文件被显式哈希：1 entrypoint、1 environment lock、9 config、35 source、25 tests、1 README 与 15 canonical receipts；所有 receipt status/decision、官方代码 commit `205faf1b…` 与禁止路径边界均通过。独立新目录重跑 manifest CSV byte-identical，完整 suite 64/64。
- 防误读：这证明“当前实现/证据集合”可检测漂移，不证明分数、候选新颖性或跨机器字节一致。它读取的 canonical receipts 不包含 submission artifact、competition data 或隐藏指标，external action=false。
- 机会成本/停止：连续增加 audit CLI 会递归使 runtime/readiness 哈希失效；本轮已用 v3/v8 完成最后级联。除真实 hash drift、赛规变化或 ≥0.0035 独立提分下界，不再新增元审计，控制面冻结到 D30。

## 外部公开情报

### E-KAGG-001 — Farming-score 梯度与 rating 收敛讨论（I）

- 来源：Kaggle 社区讨论，<https://www.kaggle.com/competitions/kaggriculture/discussion/736219>
- 发布日期：页面未标；访问日期：2026-09-09。
- 内容：公开讨论认为短局 rating 波动大，部分方案以 farming-score/稳定性而非单局胜率判断策略。
- 判断：社区线索，不是官方保证。它支持“增加配对样本并观察尾部”的实验设计，但不能证明任何 fallback 有效。

### E-KAGG-002 — 规则抽象、BC/RL 与 replay meta（I）

- 来源：Kaggle 社区讨论，<https://www.kaggle.com/competitions/kaggriculture/discussion/738079>、<https://www.kaggle.com/competitions/kaggriculture/discussion/739273>
- 发布日期：页面未标；访问日期：2026-09-09。
- 内容：讨论提出规则抽象、行为克隆/RL，以及克隆公开 agent/replay 可能塑造 meta。
- 判断：只转化为对手分层与鲁棒性审计；不得抓取私有对手日志或以未知 replay 当标签。

### E-KAGG-003 — v43 Sparse Shop Hybrid 的可迁移边界（F/I）

- 来源：Kaggle 公开 notebook（Apache-2.0），<https://www.kaggle.com/code/kaitofukami/103-128-fresh-public-v43-sparse-shop-hybrid/comments?scriptVersionId=344404785>
- 发布日期：页面未标；访问日期：2026-09-09。
- 事实：公开方案包含可见 YARN 条件、prefix-compatible 执行和专家状态同步；标题报告 103/128 是作者材料中的结果，不是本项目 LB 保证。
- 推断：三项机制可拆成独立 guard 做新种子 A/B；三条 tape 本身高度具体，不应照抄。
- 最小实验：KG-001 上依次单开可见条件 gate、prefix 守卫、state-sync 守卫，同种子/9 对手/双座位。
- 停止：任何开关在未见种子不稳定或 P10/worst/合法性退化即回滚，分别过门前不组合。

### E-KAGG-004 — Final Bradley–Terry 的 active-agent 与双槽规则（F）

- 来源：Kaggle staff 回复，<https://www.kaggle.com/competitions/kaggriculture/discussion/732931>、<https://www.kaggle.com/competitions/kaggriculture/discussion/739410>；访问 2026-09-09。
- 事实：Final B-T 使用整场比赛期间、双方在最终时都仍 active 的 episodes；与后来 deactivated agent 的旧对局不计。团队按两个 active submissions 中较好的一个排名，第二槽可视为无下行 hedge；ties 计双方 half-win。deadline 后 play rate 可能提高，但 Kaggle 不承诺数量。
- 行动含义：最终两槽应选 error-free、互补的策略并尽量稳定保留；第三次提交或 rating reroll 会淘汰较旧 active agent，并可能让其对局从 final fit 消失。短期 live rating 不是最终目标。
- 最小验证：KG-001 与安全 anchor/新 guard 在同 seeds×opponents×seats 上报告各自 W/T/L、独占胜局与双槽 union coverage；margin 只作尾部守卫。
- 风险/停止：对手最终退场导致历史失效，无法靠积累时长保证分数；第二候选无独占胜局、运行错误或尾部退化则不替换安全槽。

### E-KAGG-005 — 官方引擎的终局 reward 与 market 截断语义（F）

- 来源：Kaggle 官方 `kaggle-environments` 仓库的 [AGENTS.md](https://github.com/Kaggle/kaggle-environments/blob/master/kaggle_environments/envs/kaggriculture/AGENTS.md)、[README.md](https://github.com/Kaggle/kaggle-environments/blob/master/kaggle_environments/envs/kaggriculture/README.md) 与 [kaggriculture.py](https://github.com/Kaggle/kaggle-environments/blob/master/kaggle_environments/envs/kaggriculture/kaggriculture.py)；访问 2026-09-09；本地固定版本 1.32.7。
- 原始事实：默认赛季为 720 turns；胜负只看季末 bank coins，ties 可发生，unsold inventory 不计。每方每回合最多处理前 10 个 market orders，超出的静默丢弃；源码在最终 DONE/reward 写入前已经处理该周期的 market queue，并将 reward 直接设为 farm money。
- 可迁移约束：终局卖货只有改变最终钱数的相对次序才改变 W/T/L；所有“append sell”实验必须先证明订单处于前 10 个位置并记录实际成交量。该引擎事实不等于 live rating 或 Final B-T 的完整统计定义；后者继续以 E-KAGG-004 的官方 staff 规则为准。
- 最小实验/停止：只允许预先固定 baseline tie/loss 池的双座位配对；逐格核对订单 index、成交/丢弃和 W/T/L。订单被截断、无胜负翻转或任何错误即停止，不以 margin-only 通过。

### E-ARC-001 — 官方赛制与 Pass@2（F）

- 来源：Kaggle 官方 overview/rules，<https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/overview>、<https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/rules>
- 发布日期：页面未标；访问日期：2026-09-09。
- 事实：提交为 `submission.json`；每个测试输入最多两次尝试，按 Pass@2；环境为 L4x4，运行上限 12 小时。页面列出 2026-10-26 报名截止和 2026-11-02 最终截止。
- 含义：所有 selector 实验必须等预算比较，并把重复 slot 计为浪费。

### E-ARC-002 — 官方任务族与数据目标（F）

- 来源：ARC Prize 官方，<https://arcprize.org/arc-agi/2>、<https://arcprize.org/competitions/2026>
- 发布日期：页面未标；访问日期：2026-09-09。
- 事实：官方以对象交互、符号解释、组合规则等维度说明 ARC-AGI-2 难度；2026 项目含技术与论文赛道。
- 含义：结构分层可以用于误差审计，但分层标签必须由 demonstrations 生成，不能使用答案或任务来源。

### E-ARC-003 — 公开强锚点与运行成本（F）

- 来源：Kaggle 公开代码页及 notebook，<https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/code>、<https://www.kaggle.com/code/christopherdaleman/arc-2026-nvarc-trm-evidence-cost-v1/input?scriptVersionId=337500370>
- 发布日期：页面未标；访问日期：2026-09-09。
- 事实：公开页面显示 NVARC/TRM 类 notebook 分数约 31.11，示例 notebook 运行约 26 分钟；这些是公开锚点，不等于私榜泛化保证。
- 含义：先研究第二次尝试的边际覆盖，成本远低于重训基础模型。

### E-ARC-004 — MPT 多视角结果是负例（N，纠错）

- 来源：MPT 论文，<https://arxiv.org/html/2605.01154v1>
- 发布日期：2026-05-01；访问日期：2026-09-09。
- 事实：evaluation 表中 pretrained-only 为 21.7%；TTT、PoE、TTT+PoE 均为 0，且失败生成率均为 100%。论文还说明模型主要按 row-major 训练，替代视图并未形成可用表示。
- 纠错：不得把 21.7% 归因于多视角、PoE 或 TTT。多视角最多是一个需要重新训练表示并在 sealed holdout 校准的低优先级置信特征假设。
- 停止：若不能先恢复有效生成率与 exact accuracy，停止该分支。

### E-ARC-005 — ARC-AGI-2 基准论文（F）

- 来源：<https://arxiv.org/abs/2505.11831>
- 发布日期：2025-05-17；访问日期：2026-09-09。
- 事实：论文定义并分析 ARC-AGI-2，强调当前系统在新型组合推理上的困难。
- 含义：Paper 线应把方法主张绑定到可复现消融，而不是只报告公开评测命中。

### E-ARC-006 — ARCANA 是待复现候选（I）

- 来源：<https://arxiv.org/abs/2607.09059>
- 发布日期：2026-07-10；访问日期：2026-09-09。
- 内容：论文提出面向 ARC 的方法与结果。
- 判断：在本地权威数据和等预算条件下复现前，只登记为候选来源，不作为提分事实。

### E-ARC-007 — Confluence/ARCgentica 是云端资源上界（F/I）

- 来源：<https://github.com/confluence-labs/arc-agi-2>、<https://github.com/symbolica-ai/arcgentica>
- 发布日期：仓库页面未标；访问日期：2026-09-09。
- 事实：Confluence README 报 public evaluation 97.92%，默认依赖 Gemini API、E2B、每输入 12 agents、最多 10 次 refinement、132 并发沙箱和 12h；ARCgentica README 报 85.28%，依赖外部模型/API 与 agent server，默认两次独立 attempt，示例成本约 $6.94/task。
- 判断：这些结果不能直接迁移成 Kaggle offline baseline。可借鉴的仅是 demonstrations 上执行候选程序并反馈修复，以及 attempt diversity 的架构抽象。
- 最小实验：在本地候选缓存上做无反馈/一次 demo 修复 × 重复/独立 slot-2 的等预算 A/B。
- 风险/停止：显式记录外部模型、沙箱、成本和 public-eval 调参污染；依赖外部 API、runner >11h30 或 sealed <+1.0pp 时，仅保留为 related-work 上界。

### E-ARC-008 — PoTRE 量化独占覆盖与 selector gap（F/I）

- 来源：<https://arxiv.org/html/2607.20268>
- 发布日期：2026-07-22；访问日期：2026-09-09。
- 事实：论文在 ARC-AGI-2 public evaluation（120 题）报告：Gemini Flash 四路候选 oracle 53、最终 synthesis 46，Spectrum Search 单独 35 且 exclusive 17；Pass@2 为 46→54。另两模型的 Pass@2 分别为 40→45、94→104。论文明确指出完美 candidate selection 仍是开放问题。
- 边界：结果依赖 Gemini 外部模型并在 public evaluation 上形成，不能作为 Kaggle offline 或 sealed 泛化证据。
- 推断：现有 NVARC/TRM/program 只有在 sealed split 确实存在 exclusive solves 和 oracle gap 时，selector 才有可提取价值。
- 最小实验：用现有缓存统计 solver-family exclusive、pairwise overlap、oracle pass@2，再比较 top2、无放回 best-distinct、折内 complementarity selector。
- 停止：sealed oracle 上界 <+1pp 或外族无独占解则不训练 selector；selector 回收不足 25% oracle gap 则保持 best-distinct。

### E-ARC-009 — 四候选无放回两次选择的公开结果（F/I）

- 来源：<https://arxiv.org/html/2604.02434>；公开代码：<https://github.com/CoreThink-AI/arc-agi-2-reasoner>
- 发布日期：2026-04-02；访问日期：2026-09-09。
- 事实：Compositional Neuro-Symbolic Reasoning 从两个独立 pipeline 的四候选池中无放回选择两次；public-eval Pass@2 为 30.8%，最佳单 solver 为 26.6%。其独立消融为 full hints+SC 24.4%、no-SC 20.5%、SC-only 17.5%。
- 边界：primary/meta-classifier 使用 Grok-4，pattern detection 使用 o4-mini/Azure OpenAI；所有分数来自 public evaluation，不能直接迁移为 offline baseline。
- 推断：对现有候选，先量化结构提示的独立贡献和 cross-solver complementarity，可能比继续增加同族随机样本更有信息价值。
- 最小实验/停止：同 E-ARC-008；所有候选池与 selector 必须在折外评估，未达到 sealed +1pp 即仅作 related work。

### E-ARC-010 — 2026 官方日期复核存在 Paper 页面差异（F）

- 来源：ARC Prize 官方 <https://arcprize.org/competitions/2026>、<https://arcprize.org/competitions/2026/arc-agi-2>、<https://arcprize.org/competitions/2026/paper>；只读复核 2026-09-09 14:25 CST。
- 事实：公开页列 competition submissions due 2026-11-02、papers due 2026-11-08；技术赛每个 test input 两次 prediction，至少一次 exact match；Paper 需要 linked Kaggle code submission 且禁止报告 train-set performance。
- 边界：页面只给日期、不含时区；此前 authenticated Kaggle 快照列技术赛 2026-11-02 23:59 UTC、Paper 2026-11-09 23:59 UTC。本次没有查询 Kaggle 当前状态。
- 行动：内部 paper cutoff 保守采用 11/08；架构/依赖/最终验证冻结日为 10/12、10/26、10/30。临近截止仍需授权后复核 Kaggle，不能把日期页外推成精确时刻。

### E-POKER-001 — 官方任务与三指标权重（F）

- 来源：Kaggle 官方 overview 与公开 metric notebook，<https://www.kaggle.com/competitions/detect-suspicious-value-transfers-in-poker/overview>、<https://www.kaggle.com/code/florianderoofr/slash-poker-competition-metric>
- 发布日期：页面未标；访问日期：2026-09-09。
- 事实：任务包含 pair、evidence 和 behavior 输出；本地官方材料确认评分权重为 Pair AP 70%、Evidence MAP@5 20%、Behavior macro AP 10%。
- 含义：只提升 Pair AP 的模型最多覆盖 70%；evidence 排序必须按 OOF 单独验证。

### E-POKER-002 — PU-aware 公开基线（I）

- 来源：Kaggle 公开 notebook，<https://www.kaggle.com/code/nomannic19/poker-collusion-pu-aware-evidence-ranker>
- 发布日期：页面未标；访问日期：2026-09-09。
- 内容：公开方案将问题视为 positive-unlabelled 并构造 evidence ranker。
- 判断：方向符合标签语义，但方法和公开分数不能替代本地玩家隔离 OOF；需要三臂 PU 消融。

### E-POKER-003 — Collusion table 的行为无关边际影响分数（F/I）

- 来源：AAAI 主论文页面 <https://ojs.aaai.org/index.php/AAAI/article/view/8674>；论文 PDF <https://poker.cs.ualberta.ca/publications/AAAI13.pdf>
- 发布日期：2013-06-30；访问日期：2026-09-09。
- 事实：论文用动作前后价值变化构造玩家间效用影响表；Marginal Impact 对每个方向计算“对 partner 的影响减去对其他同局玩家的平均影响”，再把双方相加。它不预先指定 collusion pattern。原实验是三人限注扑克、合成策略，约 100,000 hands/configuration 仍能区分多数 colluder。
- 推断：在本赛中，可用公开动作/状态训练折内价值代理，形成 family-agnostic `MI_proxy`，为未公开 `other_coordination` 提供不依赖已知行为模板的候选信号。
- 最小实验：在严格 player/pool OOF 中把 MI_proxy 作为单一新增特征和 evidence-hand rank score，对比当前 residual anchor。
- 指标/风险：三项官方指标、最差行为族、未见玩家折；重点检查 shared-hand count、座位、牌力和玩家水平混杂，以及价值模型跨折泄漏。
- 停止：无 OOF 增益或信号主要由共享手数/座位解释即删除；不使用未公开牌、ID 或行序代理。

### E-POKER-004 — 顺序博弈的条件互信息与净影响（F/I）

- 来源：Bonjour、Aggarwal、Bhargava，UAI 2022 / PMLR 180，<https://proceedings.mlr.press/v180/bonjour22a.html>；全文 <https://proceedings.mlr.press/v180/bonjour22a/bonjour22a.pdf>。发布 2022-08；访问 2026-09-09。
- 事实：论文以 state-conditioned action mutual information 定义玩家间 individual influence；在顺序博弈中按动作先后分别估计 `i→j` 和 `j→i`，再用目标玩家受到的最大 outsider influence 做净化。论文只在三人 Leduc 与合成 collusion 上验证。
- 推断：它可能把 E007 的普通 action-response 相关性拆成“局面可解释部分”和“伙伴特异净影响”，并对未公开 `other_coordination` 提供 family-agnostic 信号；不能把 Leduc 结果外推成本赛正证据。
- 最小实验：same whole-pool OOF，严格只用动作前可见 coarse state，计算平滑双向 CMI、outsider-max 净影响和 episodic concentration；作为唯一新族加到 raw95，不用 ID/row order/unknown negatives，并直接复跑 early↔late。
- 指标/成本/风险：Pair AP、worst fold、两方向 delta、worst cross-time AP、与 shared-hands 的相关/消融；中等 CPU。风险是稀疏 state、动作时序错位、曝光量混杂和与 E007 重复。
- 停止：支持不足、信号主要由 shared-hands 解释，或原主门/时间门任一失败即冻结；worst cross-time AP 仍须≥0.90。

### E-POKER-005 — Elkan–Noto 的常数校正只在 SCAR 与同尺度校准下成立（F/I）

- 来源：Elkan & Noto, *Learning Classifiers from Only Positive and Unlabeled Data*, KDD 2008，<https://cseweb.ucsd.edu/~elkan/posonly.pdf>；Bekker & Davis, *Learning from Positive and Unlabeled Data under the Selected At Random Assumption*, PMLR 94, 2018，<https://proceedings.mlr.press/v94/bekker18a.html>。访问 2026-09-09。
- 原始事实：SCAR 要求 `p(s=1|x,y=1)=c` 与 x 无关；只有此时 `p(y=1|x)=p(s=1|x)/c`。c 的首选估计是同一个 trained g 在独立、同分布 validation 中 labeled positives 的平均 g(x)。论文另明确 g 与 g/c 是正比例，若只用于排序可直接用 g。
- 关键限制：后续研究指出 SCAR 很强，SAR 下 propensity 可随属性变化；概率缩放要求 well-calibrated model。原论文也区分自然 single-training-set 与 separately sampled case-control 场景。
- 对 E012 的含义：不同模型估 c/出分、任意改 P/U 抽样权重或大量 clip-to-one 都不能自动继承原定理；c 缩放本身不可能提高 AP，clipping 只会制造 ties。必须记录 selection assumption、同模型 cross-fit、抽样权重、c/clip/unique-score 守卫，并把未证 SCAR 的结果限定为敏感性试验。

### E-POKER-006 — Bayesian pool 权重能保留 support，但区间语义不是自动的 frequentist CI（F/I）

- 来源：Rubin, *The Bayesian Bootstrap*, Annals of Statistics 9(1), 1981，DOI `10.1214/aos/1176345338`，原文 <https://people.eecs.berkeley.edu/~jordan/sail/readings/rubin.pdf>；Field & Welsh, *Bootstrapping clustered data*, JRSSB 69, 2007，<https://rss.onlinelibrary.wiley.com/doi/10.1111/j.1467-9868.2007.00593.x>；Praestgaard & Wellner, *Exchangeably Weighted Bootstraps of the General Empirical Process*, Annals of Probability 21(4), 1993，DOI `10.1214/aop/1176989011`。访问 2026-09-09。
- 原始事实：Rubin 的 Bayesian bootstrap 模拟参数后验而非直接模拟统计量抽样分布，并明确推断依赖模型假设；独立 `Exp(1)` 权重归一化等价于 Dirichlet(1,…,1) 权重。Field & Welsh 支持按完整 cluster 重采样以保留组内依赖，但强调方差一致性取决于数据模型。Praestgaard–Wellner 对 exchangeably weighted empirical process 给出的是有条件的渐近结果，不是任意小样本非线性指标的通行证。
- 对 EVP 的含义：positive pool weights 确实避免 empty-family support，并可让同一 pool 权重共享 H0/L0/L1 与跨-family queries；但 34–52 pools/fold、分层 family macro 与 AP@5 非线性使“90% confidence interval”过强。未另做结果前冻结的 coverage simulation 时，应命名为“90% paired Bayesian cluster-weight sensitivity interval”。
- 最小 amendment：seed12673、5,000 draws；每 view/outer-fold 对 eligible `table_id` 取共享正权重；精确定义 query-weighted overall、family 内 weighted mean、三 family 等权 macro 与同 draw paired delta。若坚持 frequentist CI，须先用不含真实结果的合成数据覆盖模拟验证目标覆盖率；否则只作稳定性 stop，不作显著性声明。

### E-TRAFFIC-001 — 官方公开仓库与赛题页面（F）

- 来源：<https://github.com/jacky850/trafficflowbench-public>、<https://bigdataieee.org/BigData2026/cup/>、<https://asu-trans-ai-lab.github.io/gui4gmns/trafficflowbench/>
- 发布日期：官方仓库本地固定提交日期 2026-09-04；网页未标；访问日期：2026-09-09。
- 事实：公开仓库提供 baseline/数据说明；比赛把状态估计、排队、物理一致性和 ODME 组合评分。
- 含义：所有本地标签和公式以该固定提交及 Kaggle 官方数据为准。

### E-TRAFFIC-002 — V32 是当前公开锚点，不是因果解释（F/I）

- 来源：Kaggle 公开 notebook 评论页，<https://www.kaggle.com/code/lamhuy8904/traffic-flow-bench-pipeline/comments>
- 发布日期：页面未标；访问日期：2026-09-09。
- 事实：公开页面记录约 0.71846 的结果；本地已下载并校验对应 6,985,307 行工件。
- 判断：分数可作锚点，但必须通过组件级消融才能确定 State、Physics、Queue、ODME 的贡献。

### E-TRAFFIC-003 — 物理/网络诊断参考（I）

- 来源：公开 GitHub 指南，<https://github.com/asu-trans-ai-lab/cbi_plus/blob/master/docs/TFB_CBI_GUIDE.md>
- 发布日期：页面未标；访问日期：2026-09-09。
- 内容：提供基于道路网络和物理一致性的公开诊断思路。
- 判断：可用于设计守恒残差和拓扑回退；不是比赛官方标签或保证，需在固定 Task 1 留出中验证。

### E-TRAFFIC-004 — 拥堵切换应按 link-specific cutoff 与可观测性分层（F/I）

- 来源：ASU Trans+AI Lab 官方 CBI 仓库 <https://github.com/asu-trans-ai-lab/CBI>；官方 data2SupplyModel 仓库 <https://github.com/asu-trans-ai-lab/data2SupplyModel>。
- 发布日期：仓库页面未标；访问日期：2026-09-09。
- 事实：CBI 工作流用每条 link 的 critical/cutoff speed 与时变观测速度确定拥堵起止和 duration；data2SupplyModel 把 critical/cutoff speed 作为 facility/area-type 校准参数，并在 link-period 观测缺失比例 >0.5 时放弃该时段。
- 边界：这是同实验室的公开物理工作流，不是本赛 organizer truth 或分数保证；不得用 validation/private truth 重估 cutoff。
- 推断：当前 fixed≤60 km/h residual bucket 应先替换为官方 release 中 provided cutoff 的相对阈值，并加入 >50% missingness observability gate。
- 最小实验/停止：validation/private、全 panels 只读比较 fixed60 与 cutoff-relative transition 的支持、RMSE/尾部集中度；provided cutoff 缺失/近常数、覆盖大降、另一 split 不复现或任一 panel 反转即不建候选。

### E-TRAFFIC-005 — Switching filter 需要守恒、传播方向与可观测性（F/I）

- 来源：Sun & Work, *Scaling the Kalman filter for large-scale traffic estimation*，<https://arxiv.org/abs/1608.00917>；Treiber & Helbing, *Adaptive smoothing method for traffic state identification from incomplete information*，<https://arxiv.org/abs/cond-mat/0210050>。访问 2026-09-09。
- 事实：前者用 conservation-based switching-mode model，并分别讨论 observable/unobservable modes 下估计误差的稳定/有界；后者的自适应时空滤波按 free-flow 下游传播与 congested 上游传播组合，缺测鲁棒实验的 detector spacing 条件不超过 3 km。
- 边界：均非本赛数据或评分证据，3 km 也不是普适保证；只用于约束模型结构与先验失败门。
- 最小实验：先仅用 released network 与 input masks 审计上下游可观测邻居、最长间距、不可观测段和双方向覆盖；通过后才在一个 panel 互斥月份测试 input-innovation switching filter，动态显式含 conservation，不使用 failed cutoff 或目标 truth。
- 指标/风险/停止：coverage/spacing、`S_state`、逐日/最差 panel、FD/守恒 residual、runtime；不可观测比例高、间距条件不符、confirmation不优或守恒恶化即停。

## 动态赛况快照（不可当静态常量）

### D-KAGG-20260909T085825Z（F，账户/公开回放只读快照）

- 权威来源：`kaggriculture/remote/summary_latest.json` SHA-256 `756db35945d7ffcf1ea7e3acd6682d7f57bab24ee6f1ef078f7593dc5cfcb053`；maturity receipt SHA `70b2a9b4…`，观察时间 2026-09-09 08:58:25 UTC。
- 快照：public `56102094` 为 157 局 90-11-56、rating2273.6、60.83%；hybrid `56102097` 为 146 局 88-16-42、rating2554.5、65.75%。相对 155/144 两者均新增 1-0-1，全部 `DONE`、零 stderr、零 download error。
- 用法：只描述未配对动态成熟度；不覆盖 KG006 失败、不触发 KG007/确认/提交/槽位变化。项目研究 scope 已封存，后续只由静默 heartbeat 在实质变化时追加新时间戳。

### D-KAGG-20260910T032606Z（F，账户/公开回放只读快照）

- 权威来源：`kaggriculture/remote/summary_latest.json` SHA-256 `6014c63b02b1e2bb63121806e1c4c5a3e152ad58e6d5013df0acf6ce11cf2740`，生成时间 2026-09-10T03:26:06.835808Z。
- 快照：public `56102094` 为 238 个 evaluation games，112-21-105、rating 2166.9、score-rate 51.4706%、mean 3249.14、P10 -8702、worst -52908；hybrid `56102097` 为 231 局，104-24-103、rating 2348.0、score-rate 50.21645%、mean 2769.94、P10 -5084、worst -96701。两者 non-DONE=0、stderr=0；各另有 1 局 validation self-play，未混入 evaluation counts。
- 相对变化/边界：较 157/146 快照新增 81/85 局后，两槽同时收敛到约 51%/50%；hybrid rating 仍高 181.1，但 score-rate 低约 1.25pp且 worst 更差。这是成熟度/风险纠正，不是配对 causal A/B，不覆盖 KG006 失败。
- 决策：两槽继续 active/frozen，只读观察；不触发 KG007、参数突变、确认或提交。只有结果前冻结的配对种子、多对手、双座位机制实验和另行授权才可改变槽位。

### D-KAGG-20260910T210726Z（F，账户/公开回放只读快照）

- 权威来源：`kaggriculture/remote/summary_latest.json` SHA-256 `d3ce52228c2404dcd6919b88e19ef09c52ac7c75a6c17945b275a4baabce9c69`；maturity update SHA `68b33421…`，生成 2026-09-10T21:07:26Z。
- 快照：public/hybrid 各 325 evaluation games。public 132-34-159、score-rate 45.846%、rating 2023.8、mean 1596.81、P10 -8940.6、worst -52908；hybrid 120-32-173、41.846%、rating 2116.2、mean 1193.80、P10 -5695.6、worst -96701。non-DONE=0、stderr=0。
- 新 cohort：较 295/291，public 新 30 局 4-3-23、score-rate 18.33%、mean -3178.13；hybrid 新 34 局 7-4-23、26.47%、mean -1655.94。hybrid-minus-public 为 rating +92.4、score-rate -4.0pp、mean -403.01、P10 +3245、worst -43793，仍是 mixed best-of-two。
- 决策：成熟样本进一步纠正旧乐观快照，但未配对 aggregate 不能解释 causal difference；两槽继续 active/frozen，无 upload/replacement/deactivation，禁止 KG007。

### D-POKER-20260909（F，人工快照）

- 上游人工核验日期：2026-09-09；官方比赛页：<https://www.kaggle.com/competitions/detect-suspicious-value-transfers-in-poker>
- 快照：已参赛；截止 2026-09-20 22:00 UTC；top 3 约 0.93601/0.90098/0.89765。
- 用法：只用于安排实验节奏和判断结构差距；后续更新必须带新时间戳，不覆盖本条。

### D-TRAFFIC-20260909（F，人工快照）

- 上游人工核验日期：2026-09-09；官方赛题入口：<https://www.kaggle.com/competitions/trafficflowbench>
- 快照：已参赛；截止 2026-11-07 06:55 UTC；top 3 约 0.92332/0.92116/0.87742。
- 用法：只用于安排实验节奏和判断结构差距；后续更新必须带新时间戳，不覆盖本条。

### D-TRAFFIC-20260909T105740Z（F，账户/远端只读快照）

- 权威来源：`traffic/artifacts/external_checkpoint_2026-09-09T105740Z.json`，SHA-256 `106dc05d8d4054afe4676a37da7968a57af92a23e320b7d4ca2c0a78aed40ef3`；Kaggle CLI 2.2.0 的完整单页 public leaderboard/账户提交、official Git remote HEAD/main 与 competition files 首页面。
- 事实：34 teams，top3 0.92332/0.92116/0.89922；Jiayi Du 仍 rank17、0.74733，三份账户 submission 均 COMPLETE 且 ID/分数未变。official remote/local 仍同 commit `205faf1b…`；public listing 首页无可操作变更信号，archive SHA `aa122173…` 仍为本地权威。
- 边界/判决：未读 private score、hidden labels 或 organizer-only metrics；榜位单独变化不重开停止的方法族。状态 `CURRENT_NO_ACTIONABLE_CHANGE`，继续 `HOLD_SUBMISSION_56108199`。

### C-CUHK-003 — 三模态传感器—选项语义通过等变审计但主性能门失败（F/N）

- 权威来源：`cuhk_x_large/official_receipts/2026-09-11T0352Z_sensor_option_semantics_v1_rejection.md` SHA-256 `85b9f06d…`；replay verification SHA `a5d756e4…`；v4 manifest/verification SHA `e34c0ecf…` / `baa113ce…`。
- 方法：HAU/emotion 809 个唯一 QA/clips，18 折 subject-disjoint LOSO；IMU、Radar、Skeleton 分别拟合 option-ranker，仅 all-present 且 2/3 语义多数时覆盖 owned RF OOF。未知来源 0.77777 向量与其 `parent_prediction` 列完全不进入父模型；Fresh20/VLM 不作输入或证据。
- 结果：270 个父分歧上 candidate `101/270=0.37407`，owned parent `87/270=0.32222`；固定两半净值 `+15/-1`，trial-prefix 环境代理净值 `-1/+7/+8`。24×809=`19,416` 个选项排列与 809 个同义改写均 0 语义错位，invalid=0。
- 判决/停止：虽分歧量与 parent≤0.40 通过，但 candidate≥0.60 和两个半区均正失败，故 `REJECT_NO_TEST_NO_SUBMISSION`。禁止事后置信度、subject、环境或模态子集挖掘；没有读取 test、生成测试预测/候选或提交。两次完整复放所有离散字段、指标与判决一致，仅 margin 有 ≤`3.89e-16` 末位浮点差。
- 当前状态：两份 finalists `56122653` / `56108595` 不变；v4 复现核验 114/114 artifacts、16/16 model files、2/2 candidates PASS。Large 2 小时主攻后续只推进 HAU Depth/结构优先路线；旧 Fresh20 与本传感器 v1 均冻结。

## 合规红线

- 不读取或推断隐藏标签、私榜标签、对手私有日志或未授权数据。
- 不把 ID、原始行序、文件生成顺序、提交行位置或已知公共答案映射作为模型特征。
- Poker 未标注 pair 保持 `unknown`，不自动记为负例。
- Traffic organizer-only 标签保持 `unknown`，不在本地制造伪真值。
- ARC selector 只读取 demonstrations、候选输出和与答案无关的结构特征。
- Kaggriculture 只使用公开规则、公开 agent 和自己生成的 replay；社区 rating 叙述仅作假设。
- 任何公共方案先记录许可证/规则允许范围、来源 URL 和修改点；不可复现的分数不作为证据。

## 待查问题

1. Kaggriculture 引擎胜负、Final B-T 与双槽规则已核；live matchmaking/rating 的完整更新方程仍未在官方材料中找到，不对其作因果反推。
2. ARCANA 在权威 2026 Kaggle 文件、12 小时/L4x4 等预算下能否复现。
3. Poker public LB 高分与三子指标的实际分解，公开 notebook 是否存在玩家重叠。
4. Traffic 的 State/Queue/ODME baseline 已直接绑定；仍缺官方 Queue truth、LWR/full Physics 与三项 organizer-only ODME 分量，保持 unknown 而不反推。
5. 五条线每次提交后的公开分数、代码哈希和反事实问题需追加到本账本。
