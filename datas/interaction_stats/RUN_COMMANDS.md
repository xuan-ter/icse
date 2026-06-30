
# Bootstrap 50,000 次运行命令

## 第一优先级：可能提升最显著的项目
(效应较小但置信区间不跨零的交互较多)

```powershell
# 项目 1: hyper
cd d:\MIR_LLVM_NEW\hyper\analysis\did; python analyze_interaction.py

# 项目 2: bat
cd d:\MIR_LLVM_NEW\bat\analysis\did; python analyze_interaction.py

# 项目 3: image
cd d:\MIR_LLVM_NEW\image\analysis\did; python analyze_interaction.py

# 项目 4: eza
cd d:\MIR_LLVM_NEW\eza\analysis\did; python analyze_interaction.py

# 项目 5: loop_hoisting_bench
cd d:\MIR_LLVM_NEW\loop_hoisting_bench\analysis\did; python analyze_interaction.py

# 项目 6: iterator_pipeline_bench
cd d:\MIR_LLVM_NEW\iterator_pipeline_bench\analysis_new\did; python analyze_interaction.py
```

---

## 第二优先级：标准项目
(效应中等，会有一些提升)

```powershell
# 项目 7: aggregate_scalarization_bench
cd d:\MIR_LLVM_NEW\aggregate_scalarization_bench\analysis_new\did; python analyze_interaction.py

# 项目 8: aho-corasick
cd d:\MIR_LLVM_NEW\aho-corasick\analysis\did; python analyze_interaction.py

# 项目 9: async_state_machine_bench
cd d:\MIR_LLVM_NEW\async_state_machine_bench\analysis_new\did; python analyze_interaction.py

# 项目 10: branch_cfg_bench
cd d:\MIR_LLVM_NEW\branch_cfg_bench\analysis_new\did; python analyze_interaction.py

# 项目 11: fast_image_resize
cd d:\MIR_LLVM_NEW\fast_image_resize\analysis\did; python analyze_interaction.py

# 项目 12: quinn
cd d:\MIR_LLVM_NEW\quinn\analysis\did; python analyze_interaction.py

# 项目 13: serde
cd d:\MIR_LLVM_NEW\serde\analysis_new\did; python analyze_interaction.py

# 项目 14: tokio
cd d:\MIR_LLVM_NEW\tokio\analysis\did; python analyze_interaction.py
```

---

## 第三优先级：效应已很大的项目
(2000次时已有大量显著，提升相对较小)

```powershell
# 项目 15: regex
cd d:\MIR_LLVM_NEW\regex\analysis_new\did; python analyze_interaction.py

# 项目 16: ripgrep
cd d:\MIR_LLVM_NEW\ripgrep\analysis_new\did; python analyze_interaction.py

# 项目 17: trait_test
cd d:\MIR_LLVM_NEW\trait_test\analysis_new\did; python analyze_interaction.py
```

---

## 已完成：rustls
```powershell
# rustls 已经是 50000 次并运行完毕
# 结果: 从 0 个显著交互提升到 16 个
```

---

## 全部完成后：更新汇总表
```powershell
cd d:\MIR_LLVM_NEW\datas\interaction_stats; python summarize_interactions.py
```

---

## 提示
- 您可以在不同的终端同时运行多个项目
- 每个项目运行时间约为原来的 25 倍
- 原始结果已备份为 interaction_results_2000.csv
- 建议优先运行第一优先级的项目，观察效果

