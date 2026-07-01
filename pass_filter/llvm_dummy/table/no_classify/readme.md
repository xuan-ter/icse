# LLVM 平铺式实验矩阵说明

本文档介绍了 `llvm_experiment_matrix_flat.csv` 的结构与用途。该矩阵基于 **83 个** 通用 LLVM 优化参数，采用“平铺式”（不区分 7 大类别）的策略生成，主要用于进行单因素消融实验。

---

## 1. 实验设计逻辑

共生成 **85 组** 实验配置：

1.  **Baseline (1组)**:
    *   **ID**: `EXP_000_DEFAULT`
    *   **RUSTFLAGS**: 空
    *   **含义**: 编译器默认状态（所有优化开启）。

2.  **Global Disable (1组)**:
    *   **ID**: `EXP_001_DISABLE_ALL`
    *   **RUSTFLAGS**: 包含所有 83 个 `-C llvm-args=-disable-xxx`
    *   **含义**: 暴力关闭所有已知的 83 个通用优化，作为性能下界参考。

3.  **Single Disable (83组)**:
    *   **ID**: `EXP_ABL_xxx_<ArgName>`
    *   **RUSTFLAGS**: `-C llvm-args=-disable-xxx`
    *   **含义**: 在默认开启所有优化的情况下，**仅关闭某一个**特定的优化。
    *   **用途**: 评估该特定优化对性能的贡献（Ablation Study）。如果关闭它导致性能显著下降，说明该优化非常关键。

---

## 2. CSV 字段说明

| 字段 | 描述 |
| :--- | :--- |
| `Experiment_ID` | 实验唯一编号，如 `EXP_ABL_042_memop-opt` |
| `Type` | 实验类型 (`Baseline`, `Global_Config`, `Ablation`) |
| `Target_Arg` | 本次实验操作的参数，如 `-disable-memop-opt` |
| `RUSTFLAGS` | 核心字段，直接用于环境变量。格式为 `-C llvm-args=-disable-xxx` |
| `Description` | 人类可读说明 |

## 3. 使用方法

直接读取 CSV 并设置环境变量即可运行：

```bash
# Bash 伪代码
export RUSTFLAGS="-C llvm-args=-disable-vector-combine"
cargo build --release
```

**注意**: 这些参数都是 `disable` 类型的开关。
*   **不传参数** = 优化开启（默认）。
*   **传参数** = 优化关闭。
*   因此，本实验矩阵本质上是在做 **"减法"测试**：看少了这个优化，程序会慢多少。

## 4. 文件索引
*   **输入**: `c:\Users\21101\Desktop\实验\llvm_dummy\classification\llvm_args_categorized_7_classes.txt`
*   **输出**: `c:\Users\21101\Desktop\实验\llvm_dummy\table\no_classify\llvm_experiment_matrix_flat.csv`
