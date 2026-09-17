# Kaggle 组合控制平面 — 2026-09-17 重新立项

## 0. 适用范围与动态快照

本控制平面覆盖工作区中除 CUHK-X Small、CUHK-X Large 与 Kaggriculture
之外的全部比赛线。CUHK 与 Kaggriculture 由独立控制面负责，本文件不改写
它们的赛后状态或最终选择。

- 官方比赛 inventory 与提交列表：2026-09-16 19:30–19:38 UTC
  （2026-09-17 03:30–03:38 CST）由认证 Kaggle CLI 重新读取。
- 完整排行榜 CSV：Kaggle 生成时间 2026-09-16 19:30–19:32 UTC。
- 本机进程复核：没有任何本工作区训练、推理、提交或 Kaggle 下载进程在运行。
- 重新编排后的自动任务：TartanIMU、ARC-AGI-3、ARC Paper、Kaggriculture
  replay monitor 与全局 DDL 雷达为 ACTIVE；Poker、S6E9、Biohub、Traffic、
  ARC-AGI-2 与 CUHK 赛后任务为 PAUSED。两个高光谱赛不建立周期性
  自动任务，只允许一次性、带终止门的执行。
- 决策口径：不因为旧 README 写过 GO 就继续；用剩余时间、实时榜差、可证伪
  假设、交付成本与当前阻塞重新立项。

四类决策只有：`继续`、`换线`、`封存`、`仅交付`。

所有候选的跨赛统一门控、回执字段、重试预算与终态语义由
`PORTFOLIO_HARNESS_REBASE_2026-09-17.md` 约束；旧项目 README 中更宽松的
晋级规则不再覆盖该合同。

## 1. 组合优先级

| 优先级 | 比赛 | 实时状态 | 重新立项决策 | 未来 72 小时唯一主动作 |
|---|---|---|---|---|
| P0-1 | TartanIMU | 已加入；9/20 23:55 UTC；98/108，0.63142 | 仅交付 | 发布冻结包并完成最终报告/表单，不再训练 |
| P0-2 | Poker | 已加入；9/20 22:00 UTC；244/290，0.44388；v4.2 一次性运行不完整 | 封存 | 保存 UNKNOWN 取证回执；不重跑、不提交 |
| P0-3 | Hyperspectral OD | 已加入；9/24 16:00 UTC；0 提交，215 队；官方 UI 不暴露 notebook attachment | 封存 | 保留两次 fail-closed 回执，不再下载、训练或提交 |
| P1-1 | Tree Species HSI | 已加入；9/25 04:00 UTC；36/48，0.10387；Phase 2 未释放 | 继续（等待事件） | readiness 已通过；仅在 9/21 官方 manifest 变化时触发 |
| P1-2 | ARC-AGI-2 | 已加入；11/2 23:59 UTC；0 提交，2050 队 | 换线 | 做一次原样、可复现的公开 31.39 级 anchor，而非续调失败 V2 |
| P2 | ARC Paper | 已加入；11/9 23:59 UTC；192 队 | 仅交付 | 只维护 claim–evidence 矩阵，等待 ARC2 独立正结果 |
| P2 | ARC-AGI-3 | 未加入；11/2 23:59 UTC；3088 队 | 封存 | 只完成资格事实 gate；未通过前不 Join、不算力投入 |
| P2 | Biohub Cell Tracking | 已加入；9/29 23:59 UTC；929/3617，0.944 | 封存 | 冻结现有提交和失败 OOF，不再训练 |
| P2 | Playground S6E9 | 已加入；9/30 23:59 UTC；365/2117，0.94636 | 封存 | 保全 56107927；不追逐 1e-4 级榜差 |
| P3 | Traffic Flow Bench | 已加入；11/7 06:55 UTC；38/65，0.74733 | 封存 | 保持到 D-30，不新增实验 |
| P3 | ROGII / Nemotron / Maze / NeuroGolf | 均已截止 | 封存 | 只保留复现资产与经验，不运行任何任务 |

算力分配原则：P0 可用 Kaggle CPU/GPU，但必须通过各自冻结 gate；P1 只允许
一个高信息增益动作；P2/P3 默认 0 算力。不得用“自动任务仍 ACTIVE”替代科学
晋级证据。

## 2. P0 作战线

### 2.1 TartanIMU Challenge — 仅交付

**实时事实**

- 截止：预测和公开权重 2026-09-20 23:55 UTC；报告/最终表单使用更严格的
  2026-09-23 23:59 EDT。
- 当前最好提交：E003 / `56117057` / Public `0.63142`，实时第 98/108；
  榜首 `0.22543`，Top 10 `0.31621`。
- 官方全测试服务：`0.53485`；冻结冷启动重放 117.42 秒、723,648,512 bytes，
  CSV byte-identical。
- 69 MB 权重与代码、5 页 IEEE 报告、89 条逐序列结果均已完成。
- 用户既有事实已写入报告源：Jiayi Du；Stiftung Louisenlund, Germany；
  `jiayi.du@mail.louisenlund.de`。公开仓库
  `https://huggingface.co/duj626/tartanimu-e003` 已创建，报告和 prediction URL
  已定稿；但冻结 release 文件尚未上传，HF CLI 仍未认证，Google Form 也尚未
  最终发送。现有只读令牌不能完成上传，需写权限或经确认的浏览器上传。

**原核心假设**

官方共享 ResNet–LSTM 的连续输出加 493 个 IMU/context 特征，再用一个统一
CatBoost 头，可在不做平台路由的前提下跨平台泛化；增加树数可继续改进。

**新事实与判决**

假设在工程和合规上成立，但在榜单上不具竞争性：验证改进没有缩小到 Top 10
所需的约 0.315 绝对差距。继续做 drone 专项或树数扫描已没有时间价值。

**新命题**

当前唯一正收益不是模型，而是把已经完整、可复现、合规的研究包变成有效官方
交付，避免已有工作因缺公开链接/表单而不被计入。

**72 小时唯一主动作**

发布冻结 `tartan_imu/release/` 到一个公开 HF 仓库；获得模型/代码与精确 CSV
公共 URL；替换报告最后两个链接，重编译并视觉检查；用 E003 的 immutable CSV、
最终 PDF 和公开链接提交最后一份 organizer Form。

**停止条件**

- 从现在起禁止新模型、参数、数据或 Kaggle prediction submission。
- 发布包与本地 SHA/冷启动输出任一不一致即停止发送，先修交付而非训练。
- 2026-09-20 12:00 CST 前仍没有公共仓库或用户认证表单通道，则升级为人工阻塞；
  不以新实验替代交付。

**监督映射**

现有 `ddl-tartanimu-4` 仅为交付监督保持 ACTIVE，不得启动实验；最终外部表单
发送必须保留用户可见确认与回执。

### 2.2 Detect Suspicious Value Transfers in Poker — 封存

**实时事实**

- 截止 2026-09-20 22:00 UTC；当前 `56106882` 得分 `0.44388`、第 244/290；
  榜首 `0.93827`，Top 15 `0.89897`。
- v4.2 source audit 已通过；一次性结果授权在 2026-09-17 已消费，但执行只留下
  outer 0/1 两个中间折，缺少 outer 2/3/4、终态指标和异常回执。残留进程已停止。
- 指标权重为 70% Pair AP、20% Evidence MAP@5、10% Behavior macro AP。

**原核心假设**

confirmed-only 的高 OOF Pair AP（约 0.948）会迁移到广泛 evaluation pair；
行为家族可路由 evidence ranker。

**新事实与判决**

核心假设已被公榜否定。confirmed negative 的选择机制与 evaluation population
不同；原 OOF 测到的是标注选择，而不是线上总体排序。即使 evidence 分量做到
完美，也无法单独弥合约 0.49 总分差。

**新命题**

最后值得回答的不是“再调一个 pair 模型”，而是 v4.2 在严格 pool 隔离、嵌套
family routing、时间迁移和 metric-local coverage 下，是否能证明 evidence 模块
有真实且稳定的独立信息；若不能，就终止整场。

**72 小时主动作终态**

一次性 hash-bound v4.2 运行未完整结束。只读取证确认没有任何合法指标可计算或
外推，终态为 `INCOMPLETE_UNKNOWN_TERMINATION`：这既不是科学成功，也不是科学
失败。授权不可重发，因此 Poker 线封存；不得续跑、生成 v4.3 或提交。

**停止条件**

- owned end-to-end Evidence MAP@5 未达到 `0.40`，或最差时间方向低于 `0.25`，
  或任一 coverage/hash gate 失败：立即封存，无提交。
- 即便 evidence 通过，若 pair 的 sealed pool/time gate 仍不能证明相对 E001 的
  稳定改进，不生成候选。
- 最多一个新提交，而且必须由冻结离线门自动产生；否则保持 `56106882`。

**监督映射**

`kaggle-poker-4` 已 PAUSED。取证回执为
`poker/work/EVP_v4_2_incomplete_unknown_termination.json`。只有用户明确批准一个
全新的机制和执行预算时才可重新立项，不能借“补完旧运行”绕过一次性授权。

### 2.3 Hyperspectral Object Detection Challenge — 封存

**实时事实**

- 截止 2026-09-24 16:00 UTC；已加入，215 队，尚无提交；榜首 `0.67943`，
  Top 15 `0.64687`，约第 49 名为 `0.61634`。
- 官方 payload 约 15.65 GB，本机无法同时安全保存 archive 与解压副本；正确路径
  是私有 Kaggle T4。
- 旧 mount smoke 已取消；2026-09-17 新跑的 v3 version 1 和 version 2 均在
  读取任何比赛文件前 fail closed。v1 排除了错误的 `/competitions/` 路径；v2
  证明 CLI push 实际没有把声明的 competition source 附着进 runtime。两次均无
  训练、推理、GPU、下载或提交。

**原核心假设**

16-band mosaic 用官方允许的 `[5,8,13]` pseudo-RGB，配一个 COCO 预训练
YOLO11m 单 checkpoint，可以作为第一竞争基线；旧方案使用随机图像 80/20 split。

**新事实与判决**

模型假设还未被测试，当前根阻塞是 Kaggle 数据附着。随机图像 split 对同一场景
存在过度乐观风险，不应继续作为晋级依据。连续第三次改路径没有信息价值。

2026-09-17 的官方 UI 复核补全了终态证据：已登录账号能打开比赛 Data 页并读取
完整 15.65 GB 文件清单，但比赛导航没有 Code 页；直接访问该比赛的 `/code`
页面返回 “We can't find that page”。在既有私有 notebook 的 Add Input →
Competition Datasets 中，用精确 slug、完整标题、`Hyperspectral` 与
`Object Detection Challenge 2026` 检索都未出现该比赛源。因而官方 UI 当前没有
暴露可验证的 competition-source attachment 路径。

**新命题**

先在 Kaggle UI 明确附着已加入的 competition source，并由远端 metadata 和文件
清单双重证明；挂载通过后，以空间/采集组隔离验证的 pseudo-RGB 单模型作为唯
一基线。基础设施与科研不得捆绑成一次盲跑。

**72 小时主动作终态**

官方 UI attachment 复核已完成且失败；这满足冻结停止条件。HOD 转为封存：不再
本地下载 15.65 GB、不重跑 mount、不启动 T4 baseline、不创建试探性提交。只有
官方后来新增 Code/attachment 入口或主办方提供明确且可审计的新传输路径时，才
允许重新立项，而不是自动恢复旧方案。

**停止条件**

- UI 不暴露可验证 attachment，或明确附着后 mount gate 仍不 PASS：本场封存，
  不再改路径/重跑。前一条件已于 2026-09-17 触发。
- mount PASS 后，单 YOLO baseline 必须在 12 小时内完成、空间隔离
  `mAP@[.5:.95] >= 0.30` 且提交 schema 全过；否则不提交并封存。
- 第一份合法公榜若 `<0.55`，不追逐 Phase 2；若 `>=0.60` 才允许一个单变量
  band/threshold follow-up。中间区间只保留 baseline，不扩大战线。

**监督映射**

不建立自动任务；先前临时 mount→baseline 任务已到终态并停止，禁止周期性空跑。
终态收据：
`hyperspectral_od_2026/runs/hsi_mount_smoke_v3_version1_path_failure_and_v2_preflight.md`。

## 3. P1 作战线

### 3.1 Hyperspectral Tree Species Identification — 换线

**实时事实**

- 截止 2026-09-25 04:00 UTC；Phase 2 数据 9/21 发布；48 个有效队伍。
- 当前 `56120914` 得分 `0.10387`、第 36/48；排除两个官方/测试 artifact 后，
  第 2 名 `0.50275`，Top 6 约 `0.24270`。
- 现有最好离线为 3x3 mean + LightGBM，region OOF OA `0.68814`、AA
  `0.62649`，但线上只有 `0.10387`，表明当前验证不能代表跨场景泛化。

**原核心假设**

光谱统计特征加 3x3 空间均值可在 connected-region holdout 上代表测试场景；
增加每类样本可继续提升。

**新事实与判决**

OOF→LB 的巨大坍塌否定了验证代理；10k/class follow-up 也未同时提升 OA/AA。
继续 Phase 1 LightGBM 容量/窗口微调是局部最优。

**新命题**

最终阶段的关键是跨场景/新类别适配，而不是拟合现有场景。9/21 前只构建
Phase 2 schema、类别重映射、区域分块和 unlabeled-domain drift gate；数据发布
后使用空间分块验证的 spectral-spatial 模型，第一优先是 PCA/波段卷积或局部纹理
与光谱梯度的轻量融合，而非继续加树。

**72 小时唯一主动作**

建立 fail-closed Phase 2 readiness：自动发现 band 数、scene、label set、submission
ID/order；类别变化时拒绝复用旧 encoder/head；预注册 train-scene spatial block
fold 和一个不看榜单的首候选。9/21 前不生成新的 Phase 1 submission。

该动作已完成：2026-09-17 认证清单与 Phase 1 七个文件的字节/时间签名完全一致，
因此机器终态是 `WAIT_PHASE2_NOT_RELEASED`。动态合同门与事件脚本已通过 10 项
测试；未下载 payload、未训练、未推理、未提交。下一次只允许由 9/21 官方
manifest 真实变化触发一次。

**停止条件**

- Phase 2 文件/类别合同与预期不一致且 6 小时内不能自动适配：停止提交。
- 新方法在 spatial-block OA、AA 任一未比 `lightgbm_spatial_r1_v3` 至少提升
  `+0.03`，或最差 block 退步超过 `0.02`：不做全量推理。
- 第一份 Phase 2 合法成绩仍 `<0.15`：封存；达到 `>=0.20` 才允许一个独立
  spectral-spatial follow-up。

**监督映射**

建立一次性 Phase2-readiness 任务，9/21 数据事件触发；不创建小时级训练循环。

### 3.2 ARC-AGI-2 — 换线

**实时事实**

- 已加入；截止 2026-11-02 23:59 UTC；2050 队；尚无提交。
- 榜首 `76.94`；公开可复现 anchor 约 `31.39`。
- stable-v2 远端虽然 terminal COMPLETE，但 48/50 超时、TRM 无 candidate；
  它只证明运行过，不是泛化证据。精确规则/对象分支在 172 个官方 evaluation
  outputs 上选择 0 个 candidate。

**原核心假设**

NVARC/TRM 两个神经族加保守 agreement selector，再叠加 NeuroGolf 符号分支，
能稳定复现公开前沿并形成论文贡献。

**新事实与判决**

符号分支是负控制，stable-v2 的运行时也不合格；旧混合路线不能继续当主线。
但公开 vanilla 31.39 级 anchor 尚未由本账户完成，最基本的系统校准缺失。

**新命题**

先把“本账户能否原样、在 11.5 小时内复现一个许可清楚且 schema 完整的
31.39 级 public anchor”单独回答。只有 anchor 成功后，才允许一个具有独立
held-out 改进的 selector/solver 变量。

**72 小时唯一主动作**

复制一个依赖完整、许可明确的 public vanilla notebook，不改算法；固定 assets、
GPU、submission schema 与 runtime guard，跑一次私有 reproducibility execution。

**停止条件**

- runtime `>11h30`、schema 不完整或 Public `<29.0`：只允许一次依赖/运行时修复；
  再失败则封存 ARC2 执行线。
- anchor 未成功前禁止继续 stable-v2、TRM optimizer、符号 overlay 或 Paper accuracy
  主张。

**监督映射**

现有 `kaggle-arc-agi-2-6` 保持 PAUSED；如监督层批准新命题，应新建一次性 anchor
任务，而不是恢复旧 V2 heartbeat。

## 4. P2/P3 冻结与条件线

### 4.1 ARC Paper Track — 仅交付

- 已加入；截止 2026-11-09 23:59 UTC；192 队；没有 code submission 可绑定。
- 原假设：把 ARC2 的 selector/符号增益写成兼具 Accuracy、Progress、Novelty 的
  论文。新事实：当前只有 systems-negative 和零候选符号控制，不能支持这些主张。
- 新命题：Paper 只做 claim–evidence registry 和负结果结构；ARC2 anchor 与至少
  `+1pp` 等算力 held-out 增益出现后才恢复完整论文。
- 决策：仅交付。72 小时只清理 claim 绑定，不开新实验。
- 停止条件：到 2026-10-10 仍无独立正结果，则正式 NO-GO 获奖论文，只保留内部
  技术报告。
- 监督：`kaggle-arc-paper-12` 可维持每日证据维护，但禁止制造“进展”。

### 4.2 ARC-AGI-3 — 封存

- 未加入；3088 队；Kaggle final 11/2，Milestone 2 为 9/30；无数据、无提交。
- 原假设：从 ARC2 迁移无污染运行时做 clean-room CPU baseline。
- 新事实：身份/资格/IP attestation 未闭合，且没有非平凡本地证据；与 3088 队前沿
  相比没有进入条件。
- 决策：封存。72 小时唯一动作是列出仍需用户亲自确认的年龄、税务、制裁/地区与
  IP 事实；不 Join、不下载、不跑 GPU。
- 停止条件：9/20 前 gate 未完整签认，则放弃 9/30 milestone，不再定时唤醒。
- 监督：`kaggle-arc-agi-3` 只允许资格 gate，不得自动把“用户愿意参赛”解释为
  法律事实。

### 4.3 Biohub Cell Tracking — 封存

- 已加入；截止 9/29 23:59 UTC；`0.944`、第 929/3617；榜首 `0.970`、Top 10
  `0.959`。
- 原假设：先复现公开 0.946，再用 embryo-isolated OOF 训练 UNet/追踪器并调
  detection/division/gap repair。
- 新事实：公开复现只落在巨大 0.944 tie band；12 epoch 超时取消，一 epoch恢复的
  OOF proxy 仅 `0.0300`，证明当前学习管线不能支持阈值优化。
- 决策：封存。72 小时不运行任何 kernel；保留 `56108120` 作为格式/复现资产。
- 停止条件：除非出现公开、许可明确、可复现且相对 0.944 至少 `+0.010` 的完整
  lineage，不重开。
- 监督：不创建 Biohub 自动任务；远端 BH-0002/0003 都已终态，无空转进程。

### 4.4 Playground S6E9 — 封存

- 已加入；截止 9/30 23:59 UTC；`0.94636`、第 365/2117；榜首 `0.94674`，Top 10
  `0.94658`。
- 原假设：干净 LightGBM、seed blend 和合法公开数据统计可产生稳健提升。
- 新事实：双 seed 已稳定，去 artifact/去外部均基本打平；XGB blend 只有
  `+0.0000212` OOF，远低于噪声；榜单差只有 1e-4 量级且拥挤。
- 决策：封存。72 小时只保全 submission `56107927` 与 hashes。
- 停止条件：没有事先定义的独立方法族在相同 folds 提升至少 `0.00010` 且双 seed
  复现，就不再训练/提交。
- 监督：`ddl-s6e9-4` 维持 PAUSED。

### 4.5 IEEE Traffic Flow Bench — 封存至 D-30

- 已加入；截止 11/7 06:55 UTC；`0.74733`、第 38/65；榜首 `0.92406`、Top 10
  `0.85558`。此前“17/34”已因队伍增加而失效。
- 原假设：Queue off-by-one 和 ODME lambda 单变量修复可累积稳定收益；事实证实
  `0.71846→0.74210→0.74733`，但后续本地机会下界均低于 `0.0035` 成本门。
- 决策：封存到 2026-10-08 D-30。72 小时零动作。
- 停止条件：没有新的独立方法族、官方规则变化或至少 `+0.01` honest local total
  implication，不解冻。
- 监督：`kaggle-traffic-8` 保持 PAUSED；只由 DDL 雷达在 D-30 唤醒 readiness。

## 5. 已截止旧赛正式封存

| 比赛 | 截止 | 最后可核事实 | 决策 |
|---|---|---|---|
| NVIDIA Nemotron | 2026-06-15 | 最好 Public 0.864；最好 Private 约 0.852 | 封存 |
| Maze Crawler | 2026-06-30 | 多次仿真提交；比赛已关闭 | 封存 |
| NeuroGolf 2026 | 2026-07-15 | 最后/最好约 6260.89 | 封存，仅复用 DSL/编译器思想 |
| ROGII Wellbore | 2026-08-05 | 最好 Public 9.150；最好记录 Private 9.416 | 封存 |

这些目录/报告可作方法资产，不再拥有进程、定时任务、提交额度或“继续优化”状态。

## 6. 组合级停止与监督规则

1. **一个比赛一个唯一主动作。** 72 小时内不得给同一比赛同时开研究、工程、
   榜单、交付四条支线。
2. **榜差决定是否研究。** 排名落后且理论上限不足以过门的比赛转为仅交付或封存，
   不因沉没成本继续。
3. **控制面先于算力。** 数据未附着、资格未确认、许可/公共 URL 未闭合时，训练
   结果不能升级状态。
4. **提交不是默认下一步。** 只有冻结离线门、schema、hash、许可、资源和停止
   条件全部通过，才产生至多一个候选。
5. **终态即停。** 已截止、两次同类基础设施失败、核心假设被公榜否定、或预注册
   gate 失败后，自动任务必须 PAUSED/过期，不能改门槛续命。
6. **监督映射去重。** Poker heartbeat 已 PAUSED；ARC Paper/ARC3 仅保留证据或
   资格职责；Tartan 只监督交付，HOD 无执行器，Tree HSI 只由 9/21 manifest
   变化事件触发；Biohub、EV、Traffic 与旧赛不新建执行器。全局 `kaggle-ddl`
   只做只读 DDL 差分，不训练、不报名、不提交。

## 7. 下一次组合复盘触发器

不按固定频率制造进展。仅在以下任一事件发生时重排优先级：

- Tartan 公共仓库/最终表单完成或失败；
- Poker 仅在用户明确批准全新机制与预算时重新触发；
- HOD 仅在官方新增可审计的 notebook attachment/传输路径时重新触发；
- Tree HSI Phase 2 数据发布；
- ARC2 原样 anchor 得到 terminal runtime/score；
- 官方规则、截止、奖励或评测数据发生实质变化。

## 8. 2026-09-17 09:18 CST 人工推进轮

本轮按“最多推进两条、必须产生新证据或有效提交”的合同重新核对 Poker、HOD、
ARC-AGI-2 与 Biohub。完整事实回执见
`PORTFOLIO_MANUAL_ADVANCE_RECEIPT_2026-09-17T0918CST.md`。

- **Poker：不执行。** 实时队伍数增至 292，账户榜单行第 246、`0.44388`；v4.2
  单次授权已消费且没有合法终态指标，继续执行会违反预注册。保持封存。
- **HOD：不执行。** 实时 216 队、仍为 0 提交；登录 UI 再次确认无 Code 页且
  Add Input 的 Competition Datasets 对精确标题/URL 返回 0。挂载门终态失败；没有
  保存新 version、下载数据、训练或提交。保持封存。
- **ARC-AGI-2：只取未来终态。** 私有 dry-run 已在 1,697 秒内通过，唯一 anchor
  submission `56287444` 仍为 `PENDING`。此时重推/重交没有信息增益且破坏单锚点
  设计；不轮询，Kaggle 发布终态时读取一次，分数 `>=29.0` 才继续。
- **Biohub：不执行。** 实时 3,625 队，账户榜单行第 943、`0.944`。BH-0004 虽已
  预注册单变量阈值 `0.965->0.950`，但基线 OOF 仅 `0.0300153`，远端权重运输尚未
  形成通过 preflight 的执行器；重建运输的预期信息收益不足。保持封存。

结论：四条候选均被现有科学/基础设施门合法挡住，本轮新训练、新 kernel、新提交
和等待型进程均为 0。下一轮仍只由第 7 节事件触发，不因“需要看起来在推进”而
重开已终态的工作。
