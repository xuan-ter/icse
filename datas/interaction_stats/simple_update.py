
import os
import re
from pathlib import Path

ROOT = Path(r"d:\MIR_LLVM_NEW")

# 找到所有脚本
patterns = [
    "*/analysis/did/analyze_interaction.py",
    "*/analysis_new/did/analyze_interaction.py",
]
scripts = []
for p in patterns:
    scripts.extend(ROOT.glob(p))

print(f"Found {len(scripts)} scripts")

updated = 0
skipped = 0
for script in scripts:
    with open(script, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已经是 50000
    if 'BOOTSTRAP_SAMPLES = 50000' in content:
        print(f"Skipping {script.parent.parent.name}: already 50000")
        skipped += 1
        continue
    
    # 备份结果
    results_file = script.parent / "interaction_results.csv"
    backup_file = script.parent / "interaction_results_2000.csv"
    if results_file.exists() and not backup_file.exists():
        import shutil
        shutil.copy2(results_file, backup_file)
    
    # 更新
    new_content = re.sub(r'BOOTSTRAP_SAMPLES\s*=\s*2000', 'BOOTSTRAP_SAMPLES = 50000', content)
    with open(script, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Updated {script.parent.parent.name}")
    updated += 1

print(f"\nDone: updated {updated}, skipped {skipped}")

