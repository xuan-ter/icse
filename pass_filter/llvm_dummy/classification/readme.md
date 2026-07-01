# LLVM 参数筛选与分类技术白皮书

本文档详细定义了 LLVM 隐藏参数（Hidden Flags）的筛选标准、分类优先级逻辑及决策过程。旨在为后续的编译器自动调优（Auto-tuning）实验提供可复现、可解释的参数集。

---

## 1. 筛选标准 (Filtering Criteria)

在从 `llvm-args=--help-hidden` 获取的 100+ 个参数中，我们严格遵循以下原则区分“通用参数”与“目标专用参数”。

### 1.1 方法论验证：为何选择 `--help-hidden` (Methodology Rationale)

选择 `RUSTFLAGS="-C llvm-args=--help-hidden"` 作为数据源并非偶然，而是基于以下技术事实的**唯一正确解**：

1.  **单一事实来源 (Single Source of Truth)**
    *   **动态注册机制**：LLVM 的命令行选项是通过 `cl::opt<T>` 全局构造函数动态注册的。只有当某个 Pass 被链接进 `rustc` 二进制文件时，其对应的参数才会出现在帮助信息中。
    *   **避免“幻觉”参数**：如果我们直接去爬 LLVM 源码或文档，可能会找到成百上千个参数，但其中许多可能因为 Rust 使用的 LLVM 版本不同、编译配置不同（如 `LLVM_ENABLE_ASSERTIONS=OFF`）而根本不存在于当前的编译器中。使用 `--help-hidden` 能保证**“所见即所得”**，列出的每一个参数都是当前编译器确实认识的。

2.  **可见性穿透 (Visibility)**
    *   **隐藏属性**：绝大多数用于调优的开关（如 `-disable-licm`）在 LLVM 源码中被标记为 `cl::Hidden`。标准的 `rustc --help` 或 `rustc -C llvm-args=--help` 默认隐藏这些开发者选项。只有显式请求 `--help-hidden` 才能通过 LLVM 的 `CommandLine` 库暴露它们。

3.  **Rust与LLVM的桥接正确性**
    *   `rustc` 提供了一个透传通道 `-C llvm-args="..."`。当我们传递 `--help-hidden` 时，Rust 编译器实际上是在初始化 LLVM 后端时，将此请求转发给了 LLVM 的参数解析器。
    *   因此，这个输出不仅仅是文本，它是 Rust 编译器内部集成的 LLVM 库**自我反省 (Introspection)** 的结果，具有最高的权威性。

### 1.2 判定原则：源码归属权 (Source of Truth)
我们依据 LLVM 源码中参数定义的文件路径（`cl::opt` 所在位置）来判定其归属。

*   **通用 (Generic)**:
    *   定义在 `llvm/lib/Transforms/` (Scalar, Vectorize, IPO, Utils)
    *   定义在 `llvm/lib/CodeGen/` (且不依赖特定 Target)
    *   定义在 `llvm/lib/Analysis/`
*   **架构专用 (Target-Specific)**:
    *   定义在 `llvm/lib/Target/<Arch>/` 目录下。
    *   **判定逻辑**：如果一个 Flag 仅由某个特定后端的 `TargetMachine` 或 `ISelLowering` 读取，则它在其他架构上通常是**死代码（Dead Code）**或无效开关。

### 1.3 具体黑名单决策 (Blacklist Decisions)

| 参数 (Pattern) | 归属架构 | 判定依据 (LLVM Source Context) |
| :--- | :--- | :--- |
| `-disable-mask`, `-disable-load-widen`, `-disable-store-widen` | **Hexagon** | 定义于 `HexagonTargetMachine.cpp`。虽然名字听起来像通用向量化，但实为 Hexagon DSP 特有的宽内存访问控制。 |
| `-disable-memcpy-idiom` | **Hexagon** | 定义于 `HexagonLoopIdiomRecognition.cpp`。这是 Hexagon 专用的 Loop Idiom Pass，通用的对应物是 `-disable-loop-idiom-recognition`。 |
| `-disable-const64` | **Hexagon** | 控制 Hexagon 特有的 `CONST64` 指令生成。 |
| `-disable-bswap`, `-disable-gotol` | **BPF** | 定义于 `BPFSubtarget.cpp`。用于禁用 BPF 特定的指令生成，以兼容旧版内核 verifier。 |
| `-disable-auto-paired-vec-st` | **PowerPC** | 定义于 `PPCSubtarget.cpp`。控制 Power10 架构的成对向量存储指令生成。 |
| `-disable-atexit-...` | **Mach-O** | 定义于 `TargetLoweringObjectFileImpl.cpp`，但在逻辑上仅针对 Mach-O (Apple) 格式生效。 |

### 1.4 争议项裁决 (Gray Area Resolution)
*   **Case: `-disable-memop-opt`**
    *   *初步判断*：曾因 Hexagon 经常提及而被误判为专用。
    *   *最终裁决*：**通用**。它实际上控制 `CodeGenPrepare` 中的内存操作优化（如合并 `memcpy`），影响所有架构。
*   **Case: `-disable-machine-licm` vs `-disable-licm-promotion`**
    *   *裁决*：均为**通用**。前者作用于机器指令层（MIR），后者作用于 IR 层。虽然层级不同，但都属于通用的循环优化算法。

---

## 2. 分类逻辑与优先级 (Classification Logic)

为了支持实验矩阵（Matrix Pipeline）设计，我们将 83 个通用参数划分为 7 个互斥类别。当一个参数同时符合多个特征时，采用**优先级队列（Priority Queue）**机制进行归类。

### 2.1 优先级队列 (Priority Hierarchy)

**Rule**: `Vectorization > Loop > Memory > ControlFlow > DataFlow > Pipeline/LTO > CodeGen`

这意味着：
1.  如果一个参数既涉及 Loop 又涉及 Vectorization（如 `loop-vectorize`），归入 **Vectorization**。
2.  如果一个参数既涉及 Memory 又涉及 CodeGen（如 `store-extract`），归入 **Memory**。

### 2.2 详细分类映射表

#### 1. Vectorization (向量化) - **Priority: 1**
*   **核心特征**: 显式包含 SIMD/Vector 语义。
*   **关键词**: `vector`, `slp`, `shuffle`, `interleaved`
*   **典型参数**:
    *   `-disable-vector-combine`: 禁用向量指令组合。
    *   `-disable-slp-vectorization`: 禁用超字级并行（Superword-Level Parallelism）。
    *   `-disable-binop-extract-shuffle`: 禁用特定的 Shuffle 优化。

#### 2. Loop (循环优化) - **Priority: 2**
*   **核心特征**: 针对循环结构的变换。
*   **关键词**: `loop`, `licm` (Loop Invariant Code Motion), `lsr` (Loop Strength Reduction), `iv` (Induction Variable), `lftr` (Linear Function Test Replacement), `peeling`
*   **典型参数**:
    *   `-disable-licm-promotion`: 禁用将内存提升到寄存器的 LICM 优化。
    *   `-disable-lsr`: 禁用循环强度削减（对寻址模式影响巨大）。

#### 3. Memory (内存优化) - **Priority: 3**
*   **核心特征**: 优化 Load/Store 操作或地址计算。
*   **关键词**: `mem`, `store`, `load`, `gep` (GetElementPtr), `sink` (if combined with load/store)
*   **典型参数**:
    *   `-disable-memop-opt`: 禁用内存操作优化。
    *   `-disable-separate-const-offset-from-gep`: 禁止拆分 GEP 指令中的常量偏移（影响地址计算复杂度）。

#### 4. ControlFlow (控制流) - **Priority: 4**
*   **核心特征**: 改变基本块（Basic Block）布局或分支行为。
*   **关键词**: `branch`, `block-placement`, `tail` (Tail Call/Dup), `ifcvt` (If-Conversion), `jump`, `diamond`, `triangle`
*   **典型参数**:
    *   `-disable-block-placement`: 禁用基本块重排（极大影响 I-Cache 效率）。
    *   `-disable-early-ifcvt`: 禁用早期的 If-Conversion（将分支转为条件执行）。

#### 5. DataFlow (数据流/通用标量) - **Priority: 5**
*   **核心特征**: 经典的标量优化，不依赖特定控制流结构。
*   **关键词**: `cse` (Common Subexpression Elimination), `dce` (Dead Code Elimination), `copyprop`, `constant` (Hoisting/Prop), `gvn`, `sink` (MachineSink)
*   **典型参数**:
    *   `-disable-machine-cse`: 禁用机器码级公共子表达式消除。
    *   `-disable-copyprop`: 禁用副本传播。

#### 6. Pipeline/Profile/LTO (管线与画像) - **Priority: 6**
*   **核心特征**: 涉及编译全流程策略、跨模块优化或基于 Profile 的决策。
*   **关键词**: `lto`, `profile`, `inline` (Inlining strategies), `global`, `upgrade`, `thinlto`, `sample`
*   **典型参数**:
    *   `-disable-sample-loader-inlining`: 禁用基于采样 Profile 的内联。
    *   `-disable-vp`: 禁用值画像（Value Profiling）。

#### 7. CodeGen (代码生成) - **Priority: 7 (Fallback)**
*   **核心特征**: 剩下的所有底层代码生成优化，通常涉及寄存器分配、指令调度或特定指令序列的微调。
*   **关键词**: `sched` (Scheduling), `reg`, `peephole`, `spill`, `dag`, `2addr`, `strictnode`
*   **典型参数**:
    *   `-disable-peephole`: 禁用窥孔优化（Peephole Optimization）。
    *   `-disable-post-ra`: 禁用寄存器分配后的优化 Pass。
    *   `-disable-spill-fusing`: 禁用溢出代码融合。

---

## 3. 过程总结 (Process Summary)

1.  **Extract**: 提取所有 `disable-` 开头的参数。
2.  **Filter**: 对照 `lib/Target` 目录和已知黑名单，移除 64 个架构专用参数。
3.  **Map**: 将剩余 83 个参数输入上述“优先级队列”分类器。
4.  **Refine**: 人工复核 `Unknown` 或 `Misclassified` 的参数（例如确认 `memop-opt` 的归属）。
5. **Output**: 生成分类好的 `llvm_args_categorized_7_classes.txt`。

---

## 4. 相关文件索引 (File Index)

为了方便引用和验证，以下是本次分类工作涉及的核心文件及其在系统中的绝对路径：

### 4.1 最终产出 (Final Deliverables)
*   **7类分层结果 (Experiment Input)**:
    `c:\Users\21101\Desktop\实验\llvm_dummy\classification\llvm_args_categorized_7_classes.txt`
*   **方法论文档 (Documentation)**:
    `c:\Users\21101\Desktop\实验\llvm_dummy\classification\readme.md`

### 4.2 中间产物 (Intermediate Artifacts)
*   **通用参数集 (Generic Only - 83 items)**:
    `c:\Users\21101\Desktop\实验\llvm_dummy\classification\llvm_args_generic_only.txt`
*   **架构专用剔除集 (Target Specific / Blacklist)**:
    `c:\Users\21101\Desktop\实验\llvm_dummy\classification\llvm_args_target_specific.txt`

### 4.3 处理脚本 (Scripts)
*   **通用提取与过滤脚本**:
    `c:\Users\21101\Desktop\实验\llvm_dummy\classification\extract_generic.py`
