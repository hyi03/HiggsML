# Preprocess Protocol V1 规范附录

- `协议 ID`: `higgsml-preprocess-v1`
- `文档状态`: 文档复审通过，等待实现验证
- `日期`: 2026-09-01
- `所属 Sprint`: [`sprint-m1-02`](sprint-m1-02.md)
- `需求来源`: [`FR-001`](FR-001-adversarial-mlp-refactor.md) R2、R6、R7
- `权威平台`: 锁定的原生 `osx-arm64` `pytorch` Conda 环境（`osx.yml`）

## 1. 规范地位与安全边界

本文是 M1-02 的自包含科学协议。实现必须把本文全部冻结决定转录到
`config/preprocess_protocol_v1.yaml`；YAML 是机器可读副本，本文是评审与冲突解释的
规范来源。运行配置只能承载两个 ROOT 路径和资源参数，不能覆盖本文的 profile、哈希、
DSID、selection、归一化、特征、identity、split、序列化或 golden 规则。

流程严格 MC-only，只允许 Higgs 345060 与 ZZ 363490。不得读取、哈希、探测、预处理或
记录任何真实数据路径。未知样本键、额外路径、历史 `zz.root`/DSID 700600、输入哈希不符、
schema 不符或非有限数值均以退出码 `3` fail closed。运行时不得导入或调用 `xgboost/src`；
旧工程仅是本协议形成时的只读 characterization 证据。

## 2. 输入绑定与运行配置

### 2.1 固定样本

| 固定键 | `source_sample` | DSID | 标签 | 建议文件名 | SHA-256 | 完整 ROOT entry 数 |
|---|---|---:|---:|---|---|---:|
| `higgs` | `higgs_345060` | 345060 | 1 | `higgs.root` | `5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0` | 419,943 |
| `zz` | `zz_363490` | 363490 | 0 | `zz_363490.root` | `76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07` | 554,279 |

文件名只用于运维提示，内容哈希与唯一 DSID 才是绑定条件。`zz.root` 的历史 DSID 700600
及 SHA-256 `3d7588b897fc50a2342ef1d7b10f8c1b34f035456b2af215f62ad92525422789`
必须被拒绝。

### 2.2 运行配置白名单

`preprocess_run.example.yaml` 只允许以下精确顶层键；拒绝重复 YAML key 和任何额外键：

```yaml
schema_version: "1.0"
samples:
  higgs: {path: /read-only/path/higgs.root}
  zz: {path: /read-only/path/zz_363490.root}
resources:
  chunk_size_events: 50000
```

`samples` 必须精确包含 `higgs`、`zz`；每个样本只允许 `path`。`chunk_size_events` 必须是
正整数，只影响内存/吞吐，不得改变结果。必须完整顺序读取，`entry_stop=null`，CLI 不提供
`entry-stop`、样本、profile、selection 或 normalization 覆盖选项。输出路径只通过必填
`--run-dir` 提供，并受 M1-01 run transaction 的 allowed-root 与不可覆盖规则约束。

### 2.3 ROOT profile 与 canonical branch

Higgs 使用 `release22`：TTree `analysis`，动量单位 GeV，normalization 在 event branch 中。

| Canonical | ROOT branch |
|---|---|
| `runNumber` | `runNumber` |
| `eventNumber` | `eventNumber` |
| `channelNumber` | `channelNumber` |
| `lep_n` | `lep_n` |
| `lep_pt` | `lep_pt` |
| `lep_eta` | `lep_eta` |
| `lep_phi` | `lep_phi` |
| `lep_e` | `lep_e` |
| `lep_charge` | `lep_charge` |
| `lep_type` | `lep_type` |
| `trigE` | `trigE` |
| `trigM` | `trigM` |
| `lep_isTrigMatched` | `lep_isTrigMatched` |
| `lep_isTightID` | `lep_isTightID` |
| `lep_track_iso` | `lep_ptvarcone30` |
| `lep_calo_iso` | `lep_topoetcone20` |
| `lep_d0sig` | `lep_d0sig` |
| `lep_z0` | `lep_z0` |
| `mcWeight` | `mcWeight` |
| `xsec` | `xsec` |
| `kfac` | `kfac` |
| `filteff` | `filteff` |
| `sum_of_weights` | `sum_of_weights` |

ZZ 使用 `open_data_2020`：TTree `mini`，动量单位 MeV，normalization 不从 event branch 读取。

| Canonical | ROOT branch |
|---|---|
| `runNumber` | `runNumber` |
| `eventNumber` | `eventNumber` |
| `channelNumber` | `channelNumber` |
| `lep_n` | `lep_n` |
| `lep_pt` | `lep_pt` |
| `lep_eta` | `lep_eta` |
| `lep_phi` | `lep_phi` |
| `lep_e` | `lep_E` |
| `lep_charge` | `lep_charge` |
| `lep_type` | `lep_type` |
| `trigE` | `trigE` |
| `trigM` | `trigM` |
| `lep_isTrigMatched` | `lep_trigMatched` |
| `lep_isTightID` | `lep_isTightID` |
| `lep_track_iso` | `lep_ptcone30` |
| `lep_calo_iso` | `lep_etcone20` |
| `lep_d0sig` | `lep_tracksigd0pvunbiased` |
| `lep_z0` | `lep_z0` |
| `mcWeight` | `mcWeight` |

缺少协议声明的 branch、声明分支数组长度不一致或 channelNumber 不等于绑定 DSID 时失败。
ROOT 可以包含协议 mapping 之外的分支；reader 不读取这些分支，也不会把它们加入 canonical
event、输出表或模型特征。`source_entry` 由 reader 在读取后生成，ROOT 中不得存在或伪造同名
物理 branch。MeV profile 的 `lep_pt`、`lep_e` 除以 1000 转为 GeV；其他字段不缩放。

## 3. Selection 协议

### 3.1 固定阶段顺序

Cutflow 必须按下列 19 个键记录；`selected` 与 `m4l_analysis_window` 计数相同：

```text
read
trigger
allowed_lepton_types
tight_identification
track_isolation
calorimeter_isolation
transverse_impact_parameter
longitudinal_impact_parameter
exactly_four_good_leptons
trigger_match
lepton_pt
lepton_eta
zero_charge
valid_sfos_pairing
all_sfos_mass
z1_mass_window
z2_mass_window
m4l_analysis_window
selected
```

每个 event 先按 input profile 读取所有轻子，再按原 ROOT index 依次过滤。
`exactly_four_good_leptons` 之前的各轻子过滤阶段均要求存活轻子数至少为四；该 stage
自身要求恰好四个。

### 3.2 固定规则、顺序与边界

1. `trigger`: `bool(trigE) or bool(trigM)`，必须为真。
2. `allowed_lepton_types`: `abs(lep_type)` 必须为 11 或 13。
3. `tight_identification`: `bool(lep_isTightID)` 必须为真。
4. `track_isolation`: `lep_pt > 0` 且 `lep_track_iso / lep_pt < 0.3`。
5. `calorimeter_isolation`: `lep_pt > 0` 且 `lep_calo_iso / lep_pt < 0.3`。
6. `transverse_impact_parameter`: electron 要求 `abs(d0sig) < 5.0`，muon 要求
   `abs(d0sig) < 3.0`。
7. `longitudinal_impact_parameter`: `abs(lep_z0 / cosh(eta)) < 0.5 mm`。
8. `exactly_four_good_leptons`: 前述过滤后恰好四个。
9. `trigger_match`: 四个 good lepton 至少一个 `bool(lep_isTrigMatched)` 为真。
10. 将四个 good lepton 按 `pt` 降序稳定排序；相同 `pt` 保持 ROOT 原顺序。
11. `lepton_pt`: 排序后的四个值分别满足 `>= 20, 15, 10, 7 GeV`。
12. `lepton_eta`: electron `abs(eta) < 2.47`；muon `abs(eta) < 2.7`。
13. `zero_charge`: 四轻子整数 charge 总和必须等于 0。
14. `valid_sfos_pairing`: 必须存在两个不重叠的 same-flavour opposite-sign pair。
15. `all_sfos_mass`: 四个 good lepton 中所有可能的 SFOS pair（遍历全部二元组合，不限于
    最终选定的 Z1/Z2 partition）不变质量都必须严格 `> 5 GeV`。
16. `z1_mass_window`: 严格 `50 < mZ1 < 106 GeV`。
17. `z2_mass_window`: v1 固定模式，严格 `12 < mZ2 < 115 GeV`。
18. `m4l_analysis_window`: `105 <= m4l < 160 GeV`。

Sliding Z2 参数仍作为冻结、不可覆盖的协议字段保存，供 schema 完整性检查，但 v1
`min_mode=fixed`，不得启用：`low_m4l=140`、`high_m4l=190`、`low_min=12`、
`high_min=50`、`max=115`（单位 GeV）。所有参与比较的数值必须有限。

## 4. 重建、Base14 与 Angular5

### 4.1 四动量和 Z pairing

四动量采用 `(E, px, py, pz)`，单位 GeV：

```text
px = pt*cos(phi)
py = pt*sin(phi)
pz = pt*sinh(eta)
m  = sqrt(max(0, E^2 - px^2 - py^2 - pz^2))
pt = hypot(px, py)
phi = atan2(py, px)
```

对 index partition `((0,1),(2,3))`、`((0,2),(1,3))`、`((0,3),(1,2))`
依次枚举两个 SFOS pair。每个 partition 内距离 `Z_MASS_GEV=91.1876` 更近的 pair 为 Z1；
距离完全相等时第一个 pair 为 Z1。多个有效 partition 使用
`min((abs(mZ1-91.1876), z1_index_tuple, z2_index_tuple))` 决定唯一结果。

### 4.2 Base14

固定顺序为：

```text
lep1_pt, lep2_pt, lep3_pt, lep4_pt,
lep1_eta, lep2_eta, lep3_eta, lep4_eta,
mZ1, mZ2, pt4l, deltaR_Z1, deltaR_Z2, deltaPhi_ZZ
```

`lep1..4` 始终指 pt 降序轻子，不指 Z pair 成员。`delta_phi(a,b) =
(a-b+pi) mod (2*pi)-pi`，范围 `[-pi,pi)`；`deltaR=hypot(delta_eta,delta_phi)`；
`deltaPhi_ZZ=abs(delta_phi(phi_Z1,phi_Z2))`，范围 `[0,pi]`。

### 4.3 Lorentz boost 与退化行为

Boost 到四动量 `P` 的 rest frame 使用 `beta=P.spatial/P.E`。当 `|beta|=0` 时执行
identity boost，四动量原样返回。否则对待 boost 的 `(E,p)`：

```text
gamma = 1/sqrt(1-|beta|^2)
E' = gamma*(E-beta dot p)
p' = p + (((gamma-1)*(beta dot p)/|beta|^2)-gamma*E)*beta
```

`|beta| >= 1`、零能量、任意非有限分量、需要归一化的三向量零范数均失败，不用默认角度
替代。cosine 只容许超出 `[-1,1]` 最多 `1e-12`，随后 clip；更大越界失败。

### 4.4 Angular5 符号约定

每个 Z pair 必须恰好含 charge `-1` 与 `+1`；负轻子定义 decay orientation。令 X 为
四轻子系统，所有带 `_X` 的向量均 boost 到 X rest frame；lab beam 为 `(1,0,0,1)` 并
同样 boost。`unit(v)=v/|v|`，`signed_angle(axis,a,b)=atan2(axis dot (a cross b),
a dot b)`，最后 wrap 到 `[-pi,pi)`。

记号说明：`l1-`/`l1+` 是 Z1 的负/正轻子，`l2-`/`l2+` 是 Z2 的负/正轻子；后缀
`_F` 表示已 boost 到 frame F（例如 `l1-_X`、`l2-_Z2`）；`.spatial` 表示三动量
`(px,py,pz)`。

```text
z1_axis_X = unit(Z1_X.spatial)
beam_axis_X = unit(beam_X.spatial)
n1 = unit(l1-_X.spatial cross l1+_X.spatial)
n2 = unit(l2-_X.spatial cross l2+_X.spatial)
nprod = unit(beam_axis_X cross z1_axis_X)

cos_theta_star = clip(z1_axis_X dot beam_axis_X)
cos_theta_1 = clip(unit(l1-_Z1.spatial) dot -unit(Z2_Z1.spatial))
cos_theta_2 = clip(unit(l2-_Z2.spatial) dot -unit(Z1_Z2.spatial))
phi_decay_planes = signed_angle(z1_axis_X, n1, n2)
phi_production_plane = signed_angle(z1_axis_X, nprod, n1)
```

三个 cosine 范围 `[-1,1]`，两个 phi 范围 `[-pi,pi)`，`+pi` 表示为 `-pi`。任一退化
平面、非法 charge/pairing 或非有限输出导致输入绑定失败，不得丢行以隐藏错误。

## 5. 权重、identity 与 split

### 5.1 归一化和权重

固定 luminosity 为 `10000.0 pb^-1`，scale factor 为 `1.0`：

```text
physical_weight = luminosity_pb * xsec_pb * k_factor * filter_efficiency
                  / sum_of_weights * mcWeight
```

Higgs 的 `xsec/kfac/filteff/sum_of_weights` 从 event branch 读取；首个 event 建立样本常数，
后续 event 以 `rtol=1e-12, atol=0` 验证不变。ZZ 不读取这些 branch，固定使用
`xsec_pb=1.2564`、`k_factor=1.0`、`filter_efficiency=1.0`、
`sum_of_weights=7538705.808`。分母为零或结果非有限时失败。

每个样本在 selection 后、合并前独立计算：

```text
train_weight_i = abs(physical_weight_i) / mean_sample(abs(physical_weight))
```

若该样本 mean 为 0，则该样本全部 `train_weight=1.0`。`physical_weight` 保留符号用于
产额；优化器只使用有限、非负 `train_weight`。

### 5.2 Canonical identity

identity 精确为 `(source_sample, source_entry)`。`source_sample` 仅可取第 2.1 节两个值；
`source_entry` 是绑定 ROOT 中、selection 之前、从 0 开始的 TTree entry index，必须跨
chunk 保持连续。它只对精确 ROOT bytes/tree/entry order 有效。最终表中 identity 必须
完整且全局唯一。

Legacy `(runNumber,eventNumber,channelNumber)` 不是 identity；权威表已知有 2 个重复组、
共 4 行：Higgs event `102001` 的 source entries `173348/345900`，event `1136001` 的
source entries `340911/342358`（两组 `runNumber=284500, channelNumber=345060`）。

### 5.3 Stable split

对每一选后事件构造 ASCII/UTF-8 payload
`f"{int(channelNumber)}:{int(eventNumber)}"`，计算 BLAKE2b `digest_size=8`，将 8 bytes
按 big-endian unsigned integer 解释并 `% 10`：bucket `<6` 为 `train`，`6/7` 为
`validation`，`8/9` 为 `test`。行顺序、chunk size 不得影响 split。

M1-02 不定义五折 development fold；该规则必须在进入 OOF 实现 Sprint 前单独冻结，不能
由预处理实现猜测或写入当前输出。

## 6. 输出表与 canonical serialization

### 6.1 精确列顺序

输出 `processed/mc_events.csv.gz` 精确为 29 列：

```text
lep1_pt, lep2_pt, lep3_pt, lep4_pt,
lep1_eta, lep2_eta, lep3_eta, lep4_eta,
mZ1, mZ2, pt4l, deltaR_Z1, deltaR_Z2, deltaPhi_ZZ,
cos_theta_star, cos_theta_1, cos_theta_2,
phi_decay_planes, phi_production_plane,
m4l, label, split, physical_weight, train_weight,
source_sample, source_entry, runNumber, eventNumber, channelNumber
```

旧表中的 `mcWeight,xsec,kfac,filteff,sum_of_weights` 不进入新表，也不属于逐列 golden
比较。前 19 列是模型候选特征；M1-03 以后仍只能从中选择批准的固定 15 列。

### 6.2 行顺序

先输出全部 `higgs_345060`，按 `source_entry` 严格递增；再输出全部 `zz_363490`，同样
严格递增。每个 selected identity 恰好一行，不因 chunk size 改变。

### 6.3 Canonical CSV bytes

- UTF-8（无 BOM），header 一行，列序采用 6.1；行尾统一 LF，包括文件末尾。
- 浮点列必须有限，对每个 scalar 应用 Python 等价的 `format(value, '.17g')` token；若
  token 为 `-0`，规范化为 `0`。可以使用 pandas 或其他 writer，但必须配置并测试为产生
  完全相同 token/bytes。不使用 locale、千分位或空字符串。
- `label/source_entry/runNumber/eventNumber/channelNumber` 使用 base-10 integer，无小数点。
- `split/source_sample` 只允许协议枚举值；这些值不含 CSV 特殊字符，禁止添加空格。
- `canonical_content_sha256` 是上述完整未压缩 bytes 的 SHA-256。
- 使用 `gzip.compress(canonical_bytes, compresslevel=9, mtime=0)`；同时记录 gzip 文件
  SHA-256。跨 Python/zlib 的 gzip 文件哈希只作审计，内容等价由 canonical 内容哈希决定。

## 7. Golden 权威与等价谓词

### 7.1 已批准的权威链

从仓库根解释的 legacy locator 与已批准 SHA-256 为：

| Artifact | 路径 | SHA-256 |
|---|---|---|
| Identity manifest | `xgboost/runs/angular5-identity-mc-363490-2026-08-26-r3-arm64/artifacts/run_manifest.json` | `74ebc01ee452bf2f6a7a792d14ed1a62eefefffc6bb090a498fb76abe20273a0` |
| Identity table | `xgboost/runs/angular5-identity-mc-363490-2026-08-26-r3-arm64/processed/mc_events_source_identity.csv.gz` | `a3ffd8c53aca90dc1813d4f88f9d12113b1918a6f193b8f8ee792cdfd4621f94` |
| Enrichment manifest | `xgboost/runs/angular5-mc-363490-2026-08-26-r3-arm64/artifacts/run_manifest.json` | `ab5e283f4b6a2038a100a2a9d4e6745cccc3ee7f400ef056bcd05d3c22f28ad5` |
| 权威逐列表 | `xgboost/runs/angular5-mc-363490-2026-08-26-r3-arm64/processed/mc_events_angular5.csv.gz` | `bc31f4e65ccecc0a1962648cfe240b67d8ecc6df8eda2478b3f46c93d2f34f09` |

Cutflow lineage 由被 identity/enrichment chain 绑定的 baseline manifest
`xgboost/runs/full-baseline-363490-2026-08-11-r2/artifacts/run_manifest.json`、SHA-256
`10e0c293dd60291193019df04f4f6dd4672893dea98d23f972c8a78f21e843b8` 间接封存；权威
gate 必须先验证该 manifest，再从其 output descriptor 绑定同 run 的 `artifacts/cutflow.json`，
不得接收路径相同但 manifest 未绑定的 cutflow。

该 lineage 明确是 DSID 363490 的 `full-baseline-363490-2026-08-11-r2`，不同于历史
DSID 700600/真实数据 Task 4A 的 `full-baseline-2026-08-10`；后者不是 neural golden。

### 7.2 比较规则

权威 gate 只可在锁定 `osx-arm64` 环境、两个绑定 ROOT 均可用时运行。Windows/x86 可跑
单元与 synthetic micro-ROOT 测试，但不能代替或宣称通过该 gate。

- Exact：列名/列顺序、行顺序、identity、`label`、`split`、所有整数、枚举字符串、
  行数、sample/read/selected/split counts、duplicate-group 事实。
- Cutflow：两个样本的每个固定 stage `count` 必须与第 7.1 节绑定 manifest 对应的
  `cutflow.json` exact；`efficiency_previous`、`efficiency_read`、signed/absolute weighted
  yield 按下述浮点 `rtol/atol` 比较。
- Float：19 特征、`m4l`、`physical_weight`、`train_weight` 逐元素执行
  `isclose(new, golden, rtol=1e-12, atol=1e-12, equal_nan=False)`；任一非有限值失败。
- 旧表到新表按 6.1 的 29 个同名列比较；明确排除五个旧 normalization 列。
- 不允许在看到结果后改变字段分类、容差或 golden。已知跨架构 `mZ1` 最大差异
  `9.66e-13` 被当前预注册容差覆盖，但不构成放宽其他规则的依据。

固定计数：

| 范围 | Read | Selected | Train | Validation | Test |
|---|---:|---:|---:|---:|---:|
| Higgs 345060 | 419,943 | 187,128 | 112,502 | 37,290 | 37,336 |
| ZZ 363490 | 554,279 | 11,976 | 7,174 | 2,429 | 2,373 |
| Total | 974,222 | 199,104 | 119,676 | 39,719 | 39,709 |

Development 计数为 train + validation = 159,395。若 legacy artifact 在当前设备不可用，
只可记录 `authoritative_gate_not_run`；不得把 synthetic/Windows 测试表述为全量等价。

## 8. Artifact schema V1

所有 JSON 使用 UTF-8、LF、`allow_nan=false`，包含 `schema_version: "1.0"`。

### 8.1 `artifacts/cutflow.json`

```text
schema_version
selection: {protocol_id, z2_min_mode, ordered_stages}
samples: {
  <source_sample>: {
    kind: "mc", read_count, selected_count,
    stages: {
      <stage>: {count, efficiency_previous, efficiency_read,
                signed_weighted_yield, absolute_weighted_yield}
    }
  }
}
```

Sample 顺序固定 Higgs 后 ZZ，stage 顺序固定为第 3.1 节。所有 count 为非负整数；效率与
加权产额有限；每级 count 单调不增。

### 8.2 `artifacts/mc_summary.json`

```text
schema_version, status="success", protocol_id,
samples: {<source_sample>: {dsid, label, read_count, selected_count,
  split_counts:{train,validation,test}, negative_weight_events,
  sum_physical_weight, sum_abs_physical_weight}},
totals: {read_count, selected_count, split_counts},
identity: {fields:[source_sample,source_entry], unique, duplicate_count,
  legacy_duplicate_groups, legacy_duplicate_rows},
columns: {ordered_names, row_count}
```

### 8.3 `artifacts/manifest.json`

Manifest 最后发布，至少包含：

```text
schema_version, status="success", run_type="preprocess", protocol_id,
started_at_utc, completed_at_utc,
inputs: [{source_sample, dsid, logical_path, sha256, size_bytes,
          tree_name, input_profile, momentum_unit, entry_count}],
configuration: {protocol_path, protocol_sha256, run_config_path,
                run_config_sha256, chunk_size_events, full_read:true},
outputs: [{path, sha256, size_bytes, row_count|null,
           canonical_content_sha256|null}],
schema: {ordered_columns, dtypes},
counts: {per_sample, totals},
software: {python, packages, git_commit, git_dirty},
platform: {os, machine, processor},
determinism: {row_order, csv_float_format, gzip_mtime},
performance: {wall_seconds, peak_memory_bytes}
```

Manifest 必须列出全部已发布输出：`config.yaml`、MC 表、cutflow 与 `mc_summary.json`；
只排除 manifest 自身以避免自引用。最终 manifest 的文件哈希由上层目录审计。输入在发布
前重新 stat/hash 验证未变化。
失败 run 沿用 M1-01 transaction receipt，必须包含稳定退出码、异常类型、消息和时间；
失败 run 不得含 `status=success` manifest。

## 9. CLI、测试与完成证据

CLI 精确契约：

```text
higgsml-preprocess --protocol <yaml> --run-config <yaml> --run-dir <new-path>
```

三项参数必填。usage 错误为 `2`；输入/schema/hash/protocol 为 `3`；run path/transaction 为
`4`；未预期内部错误为 `70`。成功为 `0`。

测试只可在测试运行时确定性生成 synthetic micro-ROOT，不提交 ROOT、真实数据子集或真实
MC 派生 fixture。literal expected values 可以作为小型测试常量提交。测试必须覆盖两个
profile、单位、每级 selection 边界、pairing tie-break、Base14/Angular5 符号与退化、负
权重、per-sample normalization、identity/chunk independence、split、29 列/行序、CSV/gzip
确定性、schema/hash/额外样本/700600 拒绝，以及 manifest-last/failure receipt。

权威 full gate 是条件性外部验证：artifact 缺失时 Sprint 可完成代码与 synthetic 验证，
但交付结论必须明确保留 `authoritative_gate_not_run`，不得宣称全量逐列等价已证明。
