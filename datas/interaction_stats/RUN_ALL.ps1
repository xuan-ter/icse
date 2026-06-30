
# Bootstrap 50,000 次运行命令 - PowerShell 脚本
# 可以复制单条命令在不同终端运行

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Bootstrap 50,000 次运行命令" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "========== 第一优先级 ==========" -ForegroundColor Yellow
Write-Host "cd d:\MIR_LLVM_NEW\hyper\analysis\did; python analyze_interaction.py"
Write-Host "cd d:\MIR_LLVM_NEW\bat\analysis\did; python analyze_interaction.py"
Write-Host "cd d:\MIR_LLVM_NEW\image\analysis\did; python analyze_interaction.py"
Write-Host "cd d:\MIR_LLVM_NEW\eza\analysis\did; python analyze_interaction.py"
Write-Host "cd d:\MIR_LLVM_NEW\loop_hoisting_bench\analysis\did; python analyze_interaction.py"
Write-Host "cd d:\MIR_LLVM_NEW\iterator_pipeline_bench\analysis_new\did; python analyze_interaction.py"
Write-Host ""

Write-Host "========== 第二优先级 ==========" -ForegroundColor Green
Write-Host "cd d:\MIR_LLVM_NEW\aggregate_scalarization_bench\analysis_new\did; python analyze_interaction.py"
Write-Host "cd d:\MIR_LLVM_NEW\aho-corasick\analysis\did; python analyze_interaction.py"
Write-Host "cd d:\MIR_LLVM_NEW\async_state_machine_bench\analysis_new\did; python analyze_interaction.py"
Write-Host "cd d:\MIR_LLVM_NEW\branch_cfg_bench\analysis_new\did; python analyze_interaction.py"
Write-Host "cd d:\MIR_LLVM_NEW\fast_image_resize\analysis\did; python analyze_interaction.py"
Write-Host "cd d:\MIR_LLVM_NEW\quinn\analysis\did; python analyze_interaction.py"
Write-Host "cd d:\MIR_LLVM_NEW\serde\analysis_new\did; python analyze_interaction.py"
Write-Host "cd d:\MIR_LLVM_NEW\tokio\analysis\did; python analyze_interaction.py"
Write-Host ""

Write-Host "========== 第三优先级 ==========" -ForegroundColor Gray
Write-Host "cd d:\MIR_LLVM_NEW\regex\analysis_new\did; python analyze_interaction.py"
Write-Host "cd d:\MIR_LLVM_NEW\ripgrep\analysis_new\did; python analyze_interaction.py"
Write-Host "cd d:\MIR_LLVM_NEW\trait_test\analysis_new\did; python analyze_interaction.py"
Write-Host ""

Write-Host "========== 已完成 ==========" -ForegroundColor Cyan
Write-Host "rustls 已运行完成" -ForegroundColor Cyan
Write-Host ""

Write-Host "========== 最后：更新汇总表 ==========" -ForegroundColor Magenta
Write-Host "cd d:\MIR_LLVM_NEW\datas\interaction_stats; python summarize_interactions.py"
Write-Host ""

