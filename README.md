# HiggsML

本仓库包含两个使用同一组 Monte Carlo 输入的实现：

- `neural/`：PyTorch adversarial MLP；
- `xgboost/`：XGBoost；
- `data/`：两个实现共用的本地数据，不提交到 Git。

## 初始化共享数据

从仓库根目录运行：

```powershell
python scripts/init_data.py
```

命令会创建 `data/raw/`，并准备以下两个 MC ROOT 文件：

| 本地文件 | 样本 | 官方来源 | 大小（bytes） | SHA-256 |
|---|---|---|---:|---|
| `data/raw/higgs.root` | Higgs，DSID 345060 | [CERN Open Data exactly4lep MC 记录](https://opendata.cern.ch/record/atlas-93928) | 182,051,943 | `5b9628ccd88547cda07bb1b2ccd88c153d9b2e53bd119416df496ba11aa925a0` |
| `data/raw/zz_363490.root` | continuum ZZ，DSID 363490 | [CERN Open Data record 15005](https://opendata.cern.ch/record/15005) | 179,082,866 | `76503d0cb2a015b814b43e5bc1887ea53a62b057e9ac2f812eaaec1efb1a3f07` |

初始化过程如下：

1. 根据脚本位置定位仓库根目录并创建 `data/raw/`。
2. Higgs 文件通过 CERN 官方记录 API 按 DSID 345060 和冻结文件大小解析下载项；ZZ 文件使用 record 15005 的官方直链。
3. 下载内容先写入同目录的 `.part` 临时文件。
4. 脚本流式检查文件大小和 SHA-256；不匹配时删除临时文件并失败退出。
5. 校验成功后通过原子替换发布为最终文件名，两个算法随后读取同一份数据。

重复执行是安全的：已有文件通过大小和 SHA-256 检查后会直接跳过。如果已有文件损坏或来源不明，命令默认拒绝覆盖；确认需要重新下载时使用：

```powershell
python scripts/init_data.py --force
```

也可以手工从上表的官方记录下载。Higgs 文件必须选择 DSID 345060 的 exactly4lep ROOT 文件并重命名为 `higgs.root`；ZZ 的直接下载地址为：

```text
https://opendata.cern.ch/record/15005/files/mc_363490.llll.4lep.root
```

手工放置后应保持以下目录结构：

```text
data/
└── raw/
    ├── higgs.root
    └── zz_363490.root
```

`neural/config/preprocess_run.example.yaml` 和 `xgboost/config/preprocessing_run.example.yaml` 已使用相对于各自项目目录的 `../data/raw/...` 路径。请分别从 `neural/` 或 `xgboost/` 运行项目命令。

根目录 `.gitignore` 忽略整个 `data/` 目录。ROOT 文件、临时 `.part` 文件以及以后生成的本地数据都不会进入 Git。
