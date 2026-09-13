# H4l 质量条件研究运行手册

本入口实现 [H4l 项目方案](../methods/research-project.md)的软件链路，运行命令均从仓库根目录执行。
仅处理受控 MC 或显式标记的合成事件。默认协议为 `config/protocols/h4l_protocol.json`；
其 `protocol_scope=synthetic_software_defaults_not_physics_validation` 明确表示可测试的软件默认规则，
不表示真实 MC、signed 模板近似、矩阵元参考或独立验证已经通过。

仓库只维护这一份默认 H4l 协议。旧产物仍须用产物中保存的协议快照与摘要读取；
不能因默认协议文件重命名而改写或重新绑定既有run。

## 环境与入口

沿用 Conda `pytorch`、Python 3.12 和当前 `win.yml` / `osx.yml`。推断额外依赖锁在
`requirements-research.txt`，SciPy/NumPy 等既有依赖仍使用主环境锁。安装示例：

```powershell
conda activate pytorch
python -m pip install -r requirements-research.txt
python -m pip install --no-deps -e .
higgsml --help
```

安装后的统一命令入口为 `higgsml`。
Windows 开发验证不能代替锁定原生 ARM64 权威验收。MELA 另在 Linux/WSL 环境安装，
主 Python 推断流程不会自动调用任意替代概率公式。

## 阶段与产物

每个命令必填 `--dataset atlas2020_4lep --protocol <JSON> --run-dir runs/<新目录>`。
新目录必须位于当前项目 `runs/`；成功、科学终态及失败目录都不可复用。

| 阶段 | 输入 | 核心产物 |
|---|---|---|
| `audit` | `--input-manifest`，或 `--events` / `--input-run` | 来源待核验项或 G0 统计；不读取旧 test 特征 |
| `prepare` | `--input-manifest --profile`，或已有显式合成 `--events` | `events.jsonl`、`audit.json`、来源记录 |
| `me-export` | `--input-run --backend-config` | 逐轻子输入与逐事件摘要 |
| `me-import` | `--input-run --export-run --results --reference` | 独立参考绑定的 ME 分数 |
| `train` | `--input-run --candidate --seed`；扩展时加 `--gate-run` | 有序输入、scaler、完整模型张量与 checkpoint 证据 |
| `calibrate` | `--input-run --model-run --transform raw/physical/absolute` | 冻结 CDF/阈值、模型与映射身份 |
| `templates` | `--input-run`，重复 `--calibration-run`，可附 `--t1-validation` | 所有指定候选共同质量网格、模板、G1 状态 |
| `freeze` | `--input-run --template-run`，可附完整终态清单 | assessment 前冻结的候选、网格与模板身份 |
| `infer` | `--template-run --layer T0/T1 --mu` | Asimov、可选 toys、覆盖与失败状态 |
| `mc-bootstrap` | prepared、templates、封存 evaluation plan | 固定网络条件下的配对 MC 重采样 |
| `evidence-import` | 本地只读 evidence package | 经 receipt 验证的外部证据或 pending 状态 |
| `report` | 重复 result/training/evaluation/evidence run | JSON/Markdown 结论与分析就绪 CSV |

`manifest.json` 绑定数据集、协议快照、上游产物 ID、文件 SHA256/大小、代码版本及 dirty 状态、
环境和种子。JSON 模型只包含数值张量，不使用可执行 pickle 加载。
模型、CDF 和阈值还分别校验自身摘要。产物完整性与科研资格是不同状态。
prepare写出`events.jsonl`时同步累计SHA256和字节数，使用写入收据登记并直接发布，避免写完后两次
完整重读大文件。下游每次加载已发布产物时仍会按manifest重新校验文件摘要，因此跨阶段篡改检测不变。
未预期的内部异常也保留绑定候选身份的 `internal_error` manifest 和 `failure.json`，
可纳入报告，并继续以退出码 70 报错。

## 输入与角色隔离

受控 ROOT manifest 使用 `h4l-root-input-v1`，包括 `dataset`、`mc_only: true`，以及
`files.higgs` / `files.zz`。每项包含 `path`、受控下载契约的 `sha256`、
`verified_size_bytes`、`verified_mtime_ns`。必须来自已有下载校验记录；不要为研究导出重扫旧 test 特征。
profile 必须与该数据集的封存 profile 字节一致。导出前校验来源名、大小、DSID、树/字段与原始条目数。

导出先读取身份，判定已有 development/test 划分，再请求 development entry 的轻子字段，复用旧选择、
配对、四动量和 Angular5。ROOT basket 可能同时承载邻近 test 字节；保证的是不解码 test 事件数组，
不能把它描述成底层存储从未读取混合 basket。已有 acquisition SHA 记录也不等于本次重新验证输入字节。

导出保留逐轻子 pt/eta/phi/energy/charge/flavour、配对、19 特征、m4l、y4l、物理身份、signed 权重。
事件组使用固定哈希划分 train/validation/calibration/template/assessment，比例为 40/10/20/20/10%。
产额使用 `physical_weight/(0.8 * role_probability)`，分组方差按同组行之和的平方计算。

受控 MC 的训练还要求 prepare 阶段提供 `--p0-validation`。证据 JSON 必须带
`status=validated`、dataset、protocol_sha256、source_evidence_sha256、evidence_id、independent_reference，
并完整记录 physical_definitions 下的 processes、units、four_vectors、pairing、weights、selection。
这些字段绑定已完成的外部审计记录；不能通过自行填写 validated 代替审计。合成测试则始终单列来源。

事件文件每行把身份 envelope 与特征 payload 分开；读取器先验证身份和角色哈希，才决定是否解码 payload。
训练只拟合 train 与 validation；CDF/阈值只拟合 calibration；模板只使用 template。
assessment 必须绑定冻结分析。历史反馈是否影响当前设计仍需独立来源审计。

## 自动分段脚本

`scripts/h4l_prepare.py`只运行`audit`和`prepare`，完成ROOT读取后在全局目录
`runs/h4l-prepare/prepare`产生可复用产物，输入证据位于`runs/h4l-prepare/inputs`。
G1和batch的`--run-name`只控制各自实验输出，并自动读取这份全局prepare。
例如`--run-name pilot-001`统一使用短路径`runs/h4l-train-pilot-001/`，其下分别保存`g1/`和`batch/`。
prepare不会继续训练、校准或构建模板，完成时会打印下一条G1命令：

```powershell
python scripts/h4l_prepare.py
```

prepare 默认显示单条 ROOT 事件进度，格式为
`ROOT prepare: 35%|███▌      | 251,904/718,995 events | selected: 84,210`。
`events` 计数包含已按协议跳过且未读取 payload 的条目；`selected` 是通过事件选择并写入准备产物的数量。
使用 `--no-progress` 可关闭该进度条。脚本不再输出点号等待提示或 `H4l prepare 2/2` 阶段进度条。

prepare默认不打印性能统计，但仍在`manifest.json.root_prepare_metrics`记录分文件条目与span、平均span长度、
DataFrame、角色分配、G0/P0、写入并同步摘要、artifact登记时间，并给出基于这些观测量的主导阶段判断。
显式增加`--show-prepare-metrics`后，终端每10秒输出累计处理/入选条目、ROOT span数、吞吐、RSS，以及
payload、Awkward到Python转换、选择和特征构建耗时，结束时还输出每文件汇总和最终diagnosis。
CLI最终JSON另含manifest发布耗时；这些判断只定位软件热点，不构成科学验证。

需要先用有限工作量定位时，为每个ROOT文件指定相同的eligible-entry上限：

```powershell
python scripts/h4l_prepare.py --run-root runs/h4l-prepare-diagnostic-001 --diagnostic-entries-per-file 10000 --show-prepare-metrics
```

该命令发布`diagnostic_complete`终态，不能作为train/G1的`--input-run`。诊断run目录同样不可复用；正式
prepare必须使用新的run root。development-only协议仍不会为诊断跨越test间隙读取payload。

`scripts/h4l_check.py`从已有prepared artifact运行seed 42的M0c、M2、M3、五个校准和共同模板：

```powershell
python scripts/h4l_check.py --run-name pilot-001
```

训练、校准或模板失败时，失败的G1输出目录保持不可变。修复问题后应指定新的
`--output-root`，继续传入同一个`--prepared-run`；这不会重新执行ROOT prepare。G1通过后，
脚本打印绑定同一prepared artifact和新gate run的`h4l_run.py`命令。三个脚本都接受`--protocol`，
并把选择传播到所有子命令；省略时统一使用`config/protocols/h4l_protocol.json`。

`h4l_run.py`默认执行完整的seed 42–46批次。每个seed训练M0c、M2、普通M3和15个
A/B/C/D组合，生成raw校准以及M2→M4、M3→M5的physical CDF；五个seed共享一次templates、
T1 μ=1 inference和report。完整计划共90个train、100个calibrate和3个汇总阶段。可先审计命令：

```powershell
python scripts/h4l_run.py --run-name pilot-002 --plan-only
```

显式传入`--seed 42`时只运行该seed的41个阶段，用于诊断；这种结果不能完成五种子M4/M5主比较。
完整报告同时保存逐seed组合W68、相对各自M0c的改善、配对中位数、最佳组合、组级Shapley、
二阶交互和M4/M5主比较。已有batch目录不可覆盖，因此从旧单seed流程升级时必须使用新run name
或新的`--output-root`。

### 清理脚本生成的目录

三个工作流脚本都支持`--clean`。清理模式只根据同一组目录参数计算目标并删除，不验证数据集、
协议或上游产物，也不执行任何研究阶段。`--clean`不能与`--plan-only`同时使用。

```powershell
python scripts/h4l_prepare.py --clean
python scripts/h4l_check.py --run-name 001 --clean
python scripts/h4l_run.py --run-name 001 --clean
python scripts/h4l_run.py --run-name 001 --seed 42 --clean
```

prepare清理全局根目录中的`inputs`、`audit`和`prepare`；G1只删除对应run name的`g1`；
run默认删除对应run name的`batch/all-seeds`，显式`--seed N`时只删除
`batch/seedN`。使用显式路径时，prepare接受`--run-root`，G1和run接受`--output-root`并删除
该命令指定的精确目录。G1和run清理时必须显式提供run name或output root，不会采用配置文件中的
默认输出路径。所有清理目标必须是`runs`下的真实目录；runs根目录、文件、符号链接和越界
路径都会被拒绝。

## 最小链路

以下以全局受控来源产物 `runs/h4l-prepare/prepare` 为输入。已有输出目录不可覆盖。

```powershell
higgsml train --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json --input-run runs/h4l-prepare/prepare --candidate M2 --seed 42 --run-dir runs/h4l-m2-42
higgsml calibrate --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json --input-run runs/h4l-prepare/prepare --model-run runs/h4l-m2-42 --transform physical --run-dir runs/h4l-m4-42
higgsml calibrate --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json --input-run runs/h4l-prepare/prepare --model-run runs/h4l-m2-42 --transform raw --run-dir runs/h4l-m2-raw-42
```

同样建立 M0c、M3 及 M3 的物理 CDF（M5）；`templates` 一次传入所有共同候选的 calibration run。
G0 只表示原始统计支持；G1 还要求最小矩阵完整、独立校准与模板支持、实际 T1 模型可用及其验证证据。
G1 未通过时其余种子、M6、固定200轮 λ=0、绝对权重桥接和 L1 保持阻断。
全体候选和终态记录完成后才冻结 assessment。新增协议版本不能把既有反馈重新标成独立验证。

```powershell
higgsml infer --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json --template-run runs/h4l-templates-001 --layer T0 --mu 1 --run-dir runs/h4l-t0-001
higgsml report --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json --result-run runs/h4l-t0-001 --run-dir runs/h4l-report-001
```

M2→M4、M3→M5/M5-abs 的校准不重新训练网络。M6 和 M3-fixed200 都固定选择第200轮；
前5轮 λ=0，第6–15轮线性 ramp，第16–200轮为完整目标 λ。普通 M3 的早停结果不能冒充固定轮数对照。

M5-abs校准也属于G1后的候选扩展，必须传入同prepared、同协议且passed的`--gate-run`，
否则在读取校准payload前拒绝。例如（各路径须替换为实际已验证的上游）：

```powershell
higgsml calibrate --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json --input-run runs/h4l-prepare/prepare --model-run runs/h4l-m3-42 --gate-run runs/h4l-g1-passed --transform absolute --run-dir runs/h4l-m5-abs-42
```

## 训练曲线与附录

扩展诊断模型的`history_contract`绑定逐轮损失口径：分类BCE按train类别归一化绝对权重加权，
除以train行数；adversary CE除以背景归一化绝对权重和，均由该轮更新前各batch累计。
`loss`保留batch合并loss的算术均值，不是梯度反转下的纯分类目标。无adversary时其损失为null。
每轮另存λ、validation绝对权重AUC及质量KS/分箱接受率。train质量箱固定；每轮eval模式下重算
train背景绝对权重中位数作为工作点，validation只用于评价。诊断不参与checkpoint选择。

train产出已绑定摘要的`learning-curves.png`，标记warm-up、ramp和selected epoch。
report传入M6及同种子、同分组的M3-fixed200训练run时，生成配对曲线；缺失或多个控制模型时记录
`paired_control_missing_or_ambiguous`，不自动选择另一种子或最好控制模型。历史v1模型没有分项日志，
不补造曲线。图表是训练诊断，不等于收敛证明，也不替代R2的训练样本量学习曲线。

## 数值规则与失败

软件默认 CDF 为固定分数网格上的方差加权非负、总量守恒约束估计，记录修正量和目标函数。
背景 signed 总量必须为正；不将负箱静默置零。质量切片采用预声明相邻合并、质量中心间线性插值，
同分同质量 ties 同值；质量窗口外拒绝。不能声称有限直方图 CDF 严格可逆。
当前约束求解器拒绝不受支持的同组跨箱相关性。

模板保留 signed yield、正/负权重和、sumw²、事件组协方差、有效计数与抵消指标。
有限样本未观察到事件不等于已证明的结构零。统计不足会共同合箱，仍不足则报告终态；
不会给负/零物理率加 epsilon 或改用绝对权重拟合。

T0 使用固定模板；T1 使用 pyhf 0.7.6 的逐过程/箱 shapesys。
T1 证据须绑定协议，明确 `modifier=shapesys`、`correlation=independent_process_bins`、
`auxiliary=poisson_tau_gamma`、`pyhf_version=0.7.6` 和可追溯 `evidence_id`。
简单单箱数值检查不是 bound-MC signed 近似验证。若实际组协方差违背独立箱假设，即使有标记也拒绝。
区间为 μ≥0 的 profile-likelihood χ² 构造；未找到上界或优化失败保留失败，不伪造有限区间。
低计数及 μ=0 边界的覆盖适用性仍需先导验证。

扩展诊断实现可在μ=0的model-self或冻结assessment Toy中，使用同一组观测计数额外执行`signed_mu_diagnostic`。
这条独立Poisson点估计固定名义模板和全部nuisance，允许负μ；即使主区间选择T1，也标明为
`T0_fixed_template_diagnostic`，不宣称包含T1剖面误差。`signed_mu`契约独立于原物理区间的μ≥0限制。
搜索范围为[-20,20]与逐箱`b+μs>0`支持域的交集，负物理边界取0.99999999内侧比例；不把负/零yield
替换成epsilon。没有信号灵敏度或背景不正时记录`signed_domain_unavailable`，端点最优记录
`search_bound_reached`，其计数保留但不进入有效估计均值。modeled stress不执行这条名义模板诊断。
当前默认协议不自动启用该诊断；T1剖面带符号μ需单独设计正率约束和预注册。

示例（先满足该路径的全部门槛，`--toys 500`为协议内的先导预算）：

```powershell
higgsml infer --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json --template-run runs/h4l-templates-001 --layer T0 --mu 0 --toys 500 --run-dir runs/h4l-background-model-self
```

model-self覆盖不能代替assessment验证。当前区间仍使用χ²(1)临界值；Toy只检查覆盖，
`interval_calibration=not_implemented_requires_separate_registration`。不得把500次覆盖检查写成
已经校准了区间；临界值校准及其独立验证预算需后续预注册。

T2-procedure 在外层按 calibration 事件组 bootstrap，并用各副本的同一映射同时变换模板和共同母事件。
它有独立预算和随机化范围，不是额外加到 T1 的 nuisance。首期 ±10% 扰动标为人工压力测试，
不能称为实验能标、PDF 或生成器误差。精确 Shapley 要求同实验族、逐种子完整16个值（含同流程空集），
失败/缺项不会填零。

冻结后 `infer --expectation-kind assessment --input-run ... --freeze-run ... --toys ...`
使用共同物理联合单元进行配对抽样。`--procedure t2 --layer T1` 使用协议的外层/内层预算，
此时不另传 `--toys`。`--procedure stress` 可指定 kind 为 normalization、mass、score、correlation，
direction 为 -1 或 +1，mode 为 omitted 或 modeled。modeled 使用固定 ±10% 端点的 normsys/histosys，
且将 nuisance 限制在 [-1,+1]；normal 与 shapesys Poisson 辅助观测分别生成。
固定模板 MC 相对方差会随形状扰动变化时，当前 T1 模型明确拒绝，要求进一步验证的统计契约。
压力 nuisance 边界和生成模型也需做覆盖检验，不因实现了 modifier 就视为可靠物理误差。
score/correlation 压力使用协议预声明的 `M3:42` 共同参考，freeze 同时绑定其模型和映射身份。
`--reference-candidate` 不允许改成其他候选；此类请求在 assessment claim 和 payload 解码前拒绝。

assessment 首次使用前产生持久 claim；同事件组总体重新 prepare 也不能绕过它。
后续 `--repeat-assessment` 只允许同一冻结分析与协议预算，不能用来重训、重校准或重选网格。

### 注册评价编排与增强报告

先复制 `config/examples/h4l_evaluation_plan.json` 到新的计划文件，替换其中三个全零 artifact ID，
核对预算与实验矩阵，并在查看 assessment 前封存该文件。已经查看过的运行只能标为
`exploratory_posthoc`；不得把事后补写的计划改称 preregistered。先审计命令：

```powershell
python scripts/h4l_evaluate.py --plan config/evaluations/my-plan.json `
  --prepared-run runs/h4l-prepare/prepare `
  --template-run runs/h4l-train-001/batch/all-seeds/templates `
  --freeze-run runs/h4l-freeze-001 `
  --output-root runs/h4l-evaluation-001 --plan-only
```

`--plan-only` 验证 schema、协议预算并列出25个阶段，但不要求本地 run 已存在，也不读取 assessment。
正式执行还会逐项核对 prepared/template/freeze manifest 的 artifact ID。执行内容是：一个固定网络的
calibration/template 事件组配对 bootstrap；μ=0/1/2 的 model-self 和冻结 assessment Toy；一个 T2；
16个人工压力场景；以及一个新增强报告。首次 assessment 建立 claim，后续阶段只能以
`--repeat-assessment` 重放同一冻结设计。失败副本保留在原定分母中，不自动加抽样补齐。

历史运行可不重训而生成新报告：

```powershell
higgsml report --dataset atlas2020_4lep --protocol config/protocols/h4l_protocol.json `
  --result-run runs/.../inference `
  --training-run runs/.../train/model-a --training-run runs/.../train/model-b `
  --evaluation-run runs/.../templates --evaluation-run runs/.../assessment `
  --evidence-run runs/.../evidence-arm64 `
  --run-dir runs/h4l-report-enhanced-001
```

每个路径均由 manifest 显式绑定；不要用目录扫描或文件名猜测模型、mapping 或总体关系。
主 bootstrap 的区间只解释为“固定已训练网络条件下的 calibration/template MC 事件组重采样不确定度”，
不包含重新训练和 assessment 母样本波动。T2 只重拟合 calibration mapping；压力场景均标记为人工扰动。

### 独立证据导入

待交付材料可先用 `config/examples/h4l_independent_evidence.pending.json` 生成
`external_pending` 证据 run。只有实际外部文件及其 receipt 到位后才能使用 `validated`：

```powershell
higgsml evidence-import --dataset atlas2020_4lep `
  --protocol config/protocols/h4l_protocol.json `
  --evidence-file config/evidence/arm64/package.json `
  --run-dir runs/h4l-evidence-arm64-001
```

导入器拒绝越界/符号链接文件、SHA-256或大小错误、缺少独立性依据的引用、非原生 ARM64 receipt、
缺来源的物理变化以及缺少类型专用比较摘要的包。它只验证声明和文件，不执行外部实验，也不把内部
schema 检查升级为独立科学验证。

## 外部矩阵元

`scripts/research_mela.py` 是 Linux/WSL 互操作运行器。外部 Python adapter 必须实现
`compute_probabilities(event, backend, process)`，返回非负 `p_signal` / `p_background`，并声明
`PROBABILITY_DEFINITION='kinematic_decay7_at_fixed_m4l_no_mass_pdf'`。
必须传入 adapter 文件 SHA256；结果与独立参考绑定相同 adapter、后端、配置、过程、单位和输入摘要。
运行器本身不构成 MELA 物理实现或参考验证。

仓库同时提供 [固定源码 API 的可选 MELA adapter](../methods/mela-adapter.md)。
它使用独立构建 receipt 绑定实际 extension，并将完整后端设置附在结果中；其实际概率尚需外部参考验证。

```bash
python scripts/research_mela.py --input /path/me-input.json --adapter /path/verified_mela_adapter.py --adapter-sha256 SHA256 --output /path/new-me-output.json
```

独立参考缺失、后端不匹配、缺行/重复/未知事件、非有限概率都会拒绝导入，M1/M1c 保持未完成。

冻结前的 ME 导出不包含 assessment 事件。冻结后以同一 prepared run 和 `--freeze-run`
再次执行 `me-export`，经相同后端和独立参考验证后执行 `me-import`。后续评估传入
`infer --expectation-kind assessment --input-run <prepared> --freeze-run <freeze>`
及 `--assessment-me-run <新的me-import目录>`；已有 assessment claim 时还需 `--repeat-assessment`。
补充分数必须绑定同一总体、协议，以及冻结的 adapter/后端/过程/独立参考语义；
重叠事件的输入摘要与分数必须一致，只补入缺失的 assessment 行。
冻结的模型、CDF、阈值身份保持不变，补充来源另记为上游产物。
旧临时研究产物若缺少 `me_binding` 必须重建为新 run，不能回填修改。

## 验证与解释范围

```powershell
python -m pytest tests/research -q
python -m pip check
python -m pytest -q
python -m build --wheel --no-isolation
```

真实 MC 先导、独立 MELA 参考、signed 模板近似验证、独立验证批次、完整 R1–R4 预算与论文均有独立门槛。
五个种子必须完整配对，不能删去失败种子后继续宣称主比较完成。
当前软件与科学证据边界见[当前科研状态](../validation/current-status.md)。
