# MIR Pass 筛选与分类技术白皮书

本文档详细定义了从原始 MIR Transform Passes 列表中筛选出“可调优优化集合 (Tunable Optimizations)”的方法论、分类标准及决策过程。

---

## 1. 数据来源与背景

**输入文件**: `c:\Users\21101\Desktop\实验\mir_dummy\mir_passes_transform.txt`
**包含内容**: Rust 编译器 (rustc) 中层 IR (MIR) 的所有变换 Pass，共计 51 个。

**背景**:
MIR Pass 不同于 LLVM Pass，它混合了**纯优化**（如内联）和**必要的降级/合法化**（如 ElaborateDrops）。如果不加区分地进行开关测试，会导致编译失败或运行时崩溃。因此，必须进行严格的分类筛选。

---

## 2. 筛选方法论 (Methodology)

我们采用 **"Safety First, Optimization Second"**（安全优先，优化次之）的原则，将 Pass 分为三类：

1.  **Must Keep (Lowering/Safety)**: 必须保留，禁止作为变量。
2.  **Recommended Keep (Cleanup)**: 建议保留，通常不作为变量（为了基准稳定性）。
3.  **Tunable (Optimization)**: **实验目标集合**，可以自由开关或重排。

### 2.1 判定标准

#### A. 必须剔除组 (Excluded - Lowering/Safety)
*   **Lowering (降级)**: 负责将高级 Rust 语义（Enum, Box, Drop, Intrinsics）转换为低级 MIR 或 LLVM IR 形式。
    *   *特征*: 名字包含 `Lower`, `Elaborate`, `Promote`, `Deaggregator`。
    *   *风险*: 禁用后，后端无法识别高级类型，导致 ICE (Internal Compiler Error) 或生成错误代码。
*   **Safety (安全)**: 涉及 Panic 处理、Stack Unwind 安全、UB 防护。
    *   *特征*: 名字包含 `Unwind`, `CallGuards`。
    *   *风险*: 禁用后可能破坏 Rust 的内存安全承诺。

#### B. 建议剔除组 (Excluded - Cleanup)
*   **Cleanup (清理)**: 负责标准化 CFG 或清理垃圾代码，为其他优化铺路。
    *   *特征*: 名字包含 `SimplifyCfg`, `RemoveZsts`, `SimplifyLocals`。
    *   *决策*: 虽然它们是优化，但通常作为“基建”存在。例如，如果不跑 `SimplifyCfg`，后续的 `Inline` 可能根本找不到调用点。在调优实验中，建议默认开启它们以维持一个合理的基准。

#### C. 可调优组 (Tunable - Optimization)
*   **Optimization (性能关键)**: 纯粹为了提升运行速度或减少代码体积，且不影响语义正确性。
    *   *特征*: `Inline`, `Prop` (Propagation), `DSE` (Dead Store), `SROA`, `GVN`。
    *   *价值*: 这些是实验的核心变量。

---

## 3. 详细分类清单

### 3.1 可调优优化 (Tunable - 20 items)
**文件**: `mir_tunable_optimizations.txt`

| 类别 | 包含 Pass | 作用简述 |
| :--- | :--- | :--- |
| **Inlining** | `Inline`, `ForceInline` | 性能影响最大的单一因素。 |
| **Propagation** | `CopyProp`, `DataflowConstProp`, `DestinationPropagation`, `ReferencePropagation` | 消除冗余的数据移动和计算。 |
| **DSE** | `DeadStoreElimination-initial/final` | 消除无效写入。 |
| **SROA** | `ScalarReplacementOfAggregates` | 将结构体拆解为标量，对寄存器分配至关重要。 |
| **Control Flow** | `JumpThreading`, `MatchBranchSimplification`, `EarlyOtherwiseBranch`, `UnreachableEnumBranching` | 简化复杂的分支逻辑。 |
| **Redundancy** | `GVN`, `SingleUseConsts` | 全局值编号与常量合并。 |
| **Inst Simplify** | `InstSimplify-after-simplifycfg`, `InstSimplify-before-inline` | 指令级代数化简。 |

### 3.2 被剔除/默认开启 (Excluded - 31 items)
**文件**: `mir_excluded_lowering_cleanup.txt`

*   **Lowering (绝对不能动)**:
    *   `ElaborateDrops`, `ElaborateBoxDerefs`, `AddMovesForPackedDrops` (析构相关)
    *   `LowerIntrinsics`, `LowerSliceLenCalls` (内部函数)
    *   `PromoteTemps`, `PreCodegen` (代码生成准备)
*   **Safety**:
    *   `AddCallGuards`, `AbortUnwindingCalls`
*   **Cleanup (建议默认开启)**:
    *   `SimplifyCfg-*` (所有变体)
    *   `SimplifyLocals-*` (清理栈变量)
    *   `RemoveZsts` (零大小类型清理)
    *   `RemoveNoopLandingPads`

---

## 4. 处理脚本与复现

**脚本路径**: `c:\Users\21101\Desktop\实验\mir_dummy\classify\filter_mir_passes.py`

**执行逻辑**:
1.  读取 `mir_passes_transform.txt`。
2.  使用预定义的 `lowering_passes`, `safety_passes`, `cleanup_passes` 集合进行过滤。
3.  将命中 `optimization_passes` 集合的项输出到 `mir_tunable_optimizations.txt`。
4.  其余所有项输出到 `mir_excluded_lowering_cleanup.txt`。

此分类逻辑确保了实验变量（Tunable Set）是**安全且有效**的，避免了因误关 Lowering Pass 而导致的时间浪费。
