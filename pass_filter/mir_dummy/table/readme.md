# MIR 实验矩阵说明文档

本文档详细介绍了 `mir_experiment_matrix.csv` 的生成逻辑与使用方法。该矩阵旨在系统性地评估 20 个 MIR 优化 Pass 对 Rust 程序性能的影响。

---

## 1. 实验设计架构

我们设计了 **43 组** 实验，覆盖了从全开、全关到单因素分析的完整空间。

### 1.1 实验组构成
1.  **Baseline (1组)**:
    *   **ID**: `EXP_000_DEFAULT`
    *   **配置**: 空参数（使用编译器默认设置）。
    *   **目的**: 作为所有实验的对照组（Control Group）。

2.  **Global Config (2组)**:
    *   **All ON**: 强制开启所有 20 个 Pass。
    *   **All OFF**: 强制关闭所有 20 个 Pass。
    *   **目的**: 确立性能的上下界（Upper/Lower Bound）。

3.  **Ablation Study (消融实验 - 20组)**:
    *   **配置**: 开启 19 个 Pass，**仅关闭 1 个**目标 Pass。
    *   **ID**: `EXP_ABL_xxx_<PassName>`
    *   **目的**: 评估某个 Pass 在“完全优化”状态下的**边际贡献**（Marginal Contribution）。如果关掉它性能大幅下降，说明它很重要。

4.  **Isolation Study (孤立实验 - 20组)**:
    *   **配置**: 关闭 19 个 Pass，**仅开启 1 个**目标 Pass。
    *   **ID**: `EXP_ISO_xxx_<PassName>`
    *   **目的**: 评估某个 Pass 在“裸机”状态下的**独立贡献**（Individual Contribution）。

---

## 2. 文件结构说明

生成的 CSV 文件 `mir_experiment_matrix.csv` 包含以下字段：

| 字段名 | 说明 | 示例 |
| :--- | :--- | :--- |
| **Experiment_ID** | 唯一实验标识符 | `EXP_ABL_001_CopyProp` |
| **Type** | 实验类型 | `Ablation (Leave-One-Out)` |
| **Target_Pass** | 当前关注的 Pass | `CopyProp` |
| **RUSTFLAGS** | **核心字段**：传递给 cargo/rustc 的参数 | `-Z mir-enable-passes=-CopyProp,+Inline...` |
| **Description** | 人类可读的描述 | `All ON except CopyProp is OFF` |

---

## 3. 如何运行实验

在您的实验脚本中，可以遍历 CSV 的每一行，将 `RUSTFLAGS` 列的内容注入到环境变量中。

**Bash/Shell 示例**:
```bash
# 假设您使用 csvtool 或类似工具解析 CSV
experiment_id="EXP_ABL_001_CopyProp"
flags="-Z mir-enable-passes=-CopyProp,+DataflowConstProp,..."

export RUSTFLAGS="$flags"
cargo build --release --bin benchmark_target
# 运行并记录数据...
```

**Python 示例**:
```python
import csv
import subprocess
import os

with open('mir_experiment_matrix.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(f"Running {row['Experiment_ID']}...")
        env = os.environ.copy()
        env['RUSTFLAGS'] = row['RUSTFLAGS']
        
        subprocess.run(["cargo", "bench"], env=env)
```

## 4. 相关文件
*   **输入源**: `c:\Users\21101\Desktop\实验\mir_dummy\classify\mir_tunable_optimizations.txt`
*   **生成脚本**: `c:\Users\21101\Desktop\实验\mir_dummy\table\generate_matrix.py`
*   **输出矩阵**: `c:\Users\21101\Desktop\实验\mir_dummy\table\mir_experiment_matrix.csv`
