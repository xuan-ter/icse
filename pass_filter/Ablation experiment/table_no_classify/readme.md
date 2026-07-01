# MIR + LLVM 双重禁用（Double Disable）实验矩阵说明

本文档说明了 `mir_llvm_double_disable_matrix.csv` 的结构与生成逻辑。该矩阵用于研究 **1 个 MIR Pass** 和 **1 个 LLVM Pass** 同时禁用时的交互影响（Interaction Effect）。

---

## 1. 实验输入

*   **LLVM 参数来源**: `c:\Users\21101\Desktop\实验\llvm_dummy\classification\llvm_args_categorized_7_classes.txt` (共 83 个通用参数)
*   **MIR Pass 来源**: `c:\Users\21101\Desktop\实验\mir_dummy\classify\mir_tunable_optimizations.txt` (共 20 个可调优 Pass)

## 2. 实验设计

共生成 **1661 组** 实验配置：

1.  **Baseline (1组)**:
    *   **ID**: `EXP_DBL_000_BASELINE`
    *   **RUSTFLAGS**: 空
    *   **含义**: 默认状态（全开启）。

2.  **Double Disable (1660组)**:
    *   **组合逻辑**: 83 (LLVM) × 20 (MIR) = 1660 种组合。
    *   **RUSTFLAGS 格式**: `-C llvm-args=-disable-xxx -Z mir-enable-passes=-PassName`
    *   **含义**: 在默认全开启的基础上，**同时强制关闭** 指定的一个 LLVM 优化和一个 MIR 优化。

---

## 3. 字段说明

| 字段 | 描述 |
| :--- | :--- |
| `Experiment_ID` | 实验唯一编号，如 `EXP_DBL_0042` |
| `Type` | `Double_Disable` 或 `Baseline` |
| `LLVM_Arg` | 被禁用的 LLVM 参数，如 `-disable-licm` |
| `MIR_Pass` | 被禁用的 MIR Pass，如 `CopyProp` |
| `RUSTFLAGS` | 完整的环境变量设置字符串 |
| `Description` | 人类可读说明 |

## 4. 重要提示 (RUSTFLAGS)

生成的 `RUSTFLAGS` 采用了如下格式：
```bash
-C llvm-args=-disable-xxx -Z mir-enable-passes=-PassName
```

**注意**:
1.  **MIR 开关依赖**: `-Z mir-enable-passes` 是 Rust Nightly 编译器的功能。
2.  **基线优化等级**: 本矩阵**未强制指定** `-Z mir-opt-level=3`。
    *   如果您的实验基线是默认构建（通常 mir-opt-level=1/2），某些 MIR Pass 可能本身就是关闭的，此时禁用它没有额外效果。
    *   建议在运行脚本中确保基线配置（如加上 `-Z mir-opt-level=3`）以激活这些 Pass，从而使“禁用”操作有意义。

## 5. 生成脚本
脚本位于: `c:\Users\21101\Desktop\实验\Ablation experiment\table_no_classify\generate_double_matrix.py`
