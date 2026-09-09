# 可选 JHUGenMELA 适配器契约

实现：`scripts/mela_kinematic_adapter.py`；互操作运行器：`scripts/research_mela.py`。
官方源码固定在 [JHUGenMELA 10d36ced](https://github.com/JHUGen/JHUGenMELA/tree/10d36ced1d71b5e4e21abb1c9834a02570bf31c0)。
本轮核读了该版本的 Python binding、Mela.h、Mela.cc、TUtil.cc、TVar.hh；没有在 Windows 上安装、构建或执行 MELA。

## API 与过程

`mela_binding.cpp` 的 computeP wrapper 返回浮点数；该版本提供 `Mela`、
`SimpleParticle_t(id,px,py,pz,E)`、`SimpleParticleCollection_t(list)`、
`setInputEvent`、`setProcess`、`resetInputEvent` 和 `computeP(useConstant)`。
`Mela.h` 将 computeP 定义为衰变侧计算，`computePM4l` 是独立接口，本适配器不调用它。

固定设置为：13 TeV、Higgs pole mass 125 GeV、`computeP(False)`，
信号 `HSMHiggs/JHUGen/ZZGG`，背景 `bkgZZ/MCFM/ZZQQB`，
使用该源码默认的 NNPDF30_lo_as_0130 member 0。完整设置与源码版本保存在 adapter `SETTINGS` / `PROCESS`，
并写入运行器输出的 `adapter_metadata`。该参考背景过程不能据此推断 DSID 363490 是纯 qqZZ。

## 严格输入条件

先用仓库约定从导出的轻子重建 decay7 与 m4l，再从这八个坐标构造规范的、无质量轻子、零总三动量四轻子事件。
原始 pt4l、y4l、单轻子质量和整体方位不进入 MELA。Z1/Z2 与负电轻子约定使用仓库定义，
不假定仓库角名称与 MELA 角名称天然等价。退化角、非法质量支持和无定义方向拒绝计算。

20 个合成角往返、质量壳和总动量测试证明了内部逆变换一致性。
调用约定测试使用明确的 fake module；它们不能替代独立四动量/角参考或 MELA 概率验证。

## Linux/WSL 运行绑定

在隔离目录中安装该固定源码的 MELA Python extension。上游初始化会创建 Pdfdata 链接，
因此运行器的工作目录应当独立。设置 `H4L_MELA_BUILD_RECEIPT` 指向已有构建记录 JSON：

```json
{"source_commit":"10d36ced1d71b5e4e21abb1c9834a02570bf31c0","extension_sha256":"<loaded Mela extension SHA256>"}
```

适配器核对实际加载 extension 的 SHA256。后端声明使用
`name=JHUGenMELA`、`version=<完整源码commit>`，
`configuration_sha256=configuration_digest(build_receipt)`；过程配置必须与 `PROCESS` 完全一致。
receipt 绑定与文件摘要不证明源码构建来源，独立参考仍必须审计构建与物理设置。

可在同一研究环境中生成供 `me-export --backend-config` 使用的配置：

```python
import json
from scripts.mela_kinematic_adapter import SOURCE_COMMIT, PROCESS, configuration_digest

receipt = json.load(open("mela-build-receipt.json", encoding="utf-8"))
config = {
    "backend": {"name": "JHUGenMELA", "version": SOURCE_COMMIT,
                "configuration_sha256": configuration_digest(receipt)},
    "process": PROCESS,
}
with open("backend-config.json", "x", encoding="utf-8") as output:
    json.dump(config, output)
```

运行器还要求 `--adapter-sha256`，避免对修改后的 Python adapter 沿用旧验证。
导入的 `adapter_sha256`、独立 reference 的同名字段，以及每个 `checks[]` 中的 adapter SHA 必须一致。
reference 包含独立输入、输入摘要、expected/actual 概率对、后端与过程定义及可追溯 evidence_id。
未知、重复、缺失事件或非有限/负概率都拒绝。

## 当前验证状态

可选接口及规范坐标变换已做软件测试；实际 MELA 数值运行、独立概率参考、
MC 产生过程等价性和矩阵元物理比较尚未完成。缺少环境或参考时保留明确状态，
不以测试桩或替代公式产生 M1/M1c 科学结论。
