
# Bootstrap 50,000 次升级运行指南

## 已完成
- ✅ 所有 19 个项目的 `analyze_interaction.py` 已更新为 `BOOTSTRAP_SAMPLES = 50000`
- ✅ rustls 项目已运行完成并验证（发现 16 个显著交互）
- ✅ 原始结果已备份为 `interaction_results_2000.csv`

## 待运行的项目

建议按以下顺序逐个运行（可并行运行多个项目）：

### 优先级 1：效应较小，可能收益最大
```powershell
cd d:\MIR_LLVM_NEW\hyper\analysis\did; python analyze_interaction.py
cd d:\MIR_LLVM_NEW\bat\analysis\did; python analyze_interaction.py
cd d:\MIR_LLVM_NEW\image\analysis\did; python analyze_interaction.py
```

### 优先级 2：大多数项目
```powershell
cd d:\MIR_LLVM_NEW\aggregate_scalarization_bench\analysis_new\did; python analyze_interaction.py
cd d:\MIR_LLVM_NEW\aho-corasick\analysis\did; python analyze_interaction.py
cd d:\MIR_LLVM_NEW\async_state_machine_bench\analysis_new\did; python analyze_interaction.py
cd d:\MIR_LLVM_NEW\branch_cfg_bench\analysis_new\did; python analyze_interaction.py
cd d:\MIR_LLVM_NEW\eza\analysis\did; python analyze_interaction.py
cd d:\MIR_LLVM_NEW\fast_image_resize\analysis\did; python analyze_interaction.py
cd d:\MIR_LLVM_NEW\iterator_pipeline_bench\analysis_new\did; python analyze_interaction.py
cd d:\MIR_LLVM_NEW\loop_hoisting_bench\analysis\did; python analyze_interaction.py
cd d:\MIR_LLVM_NEW\quinn\analysis\did; python analyze_interaction.py
cd d:\MIR_LLVM_NEW\regex\analysis_new\did; python analyze_interaction.py
cd d:\MIR_LLVM_NEW\ripgrep\analysis_new\did; python analyze_interaction.py
cd d:\MIR_LLVM_NEW\serde\analysis_new\did; python analyze_interaction.py
cd d:\MIR_LLVM_NEW\tokio\analysis\did; python analyze_interaction.py
cd d:\MIR_LLVM_NEW\trait_test\analysis_new\did; python analyze_interaction.py
```

## 完成后更新汇总表

所有项目运行完后：

```powershell
cd d:\MIR_LLVM_NEW\datas\interaction_stats; python summarize_interactions.py
```

## 预期改进

基于 rustls 的经验，预期看到：
- 更多置信区间不跨零的交互被标记为显著
- 特别是效应较小但稳定的交互会被检测到
- BH 校正后的 p 值精度更高

## 时间估计

每个项目运行时间约为原来的 25 倍（从 2000 到 50000）。

