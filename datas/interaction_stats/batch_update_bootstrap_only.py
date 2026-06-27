
import os
import re
from pathlib import Path

ROOT = Path(r"d:\MIR_LLVM_NEW")

def find_analyze_scripts():
    """查找所有 analyze_interaction.py 脚本"""
    scripts = []
    patterns = [
        "*/analysis/did/analyze_interaction.py",
        "*/analysis_new/did/analyze_interaction.py",
    ]
    for pattern in patterns:
        scripts.extend(ROOT.glob(pattern))
    return sorted(scripts)

def update_bootstrap_in_script(script_path, old_value=2000, new_value=50000):
    """更新脚本中的 bootstrap 迭代次数"""
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    pattern = fr"BOOTSTRAP_SAMPLES\s*=\s*{old_value}"
    replacement = f"BOOTSTRAP_SAMPLES = {new_value}"
    
    if re.search(pattern, content):
        new_content = re.sub(pattern, replacement, content)
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

def backup_results(script_path):
    """备份 2000 次的结果"""
    script_dir = script_path.parent
    results_file = script_dir / "interaction_results.csv"
    backup_file = script_dir / "interaction_results_2000.csv"
    
    if results_file.exists() and not backup_file.exists():
        import shutil
        shutil.copy2(results_file, backup_file)
        return True
    return False

def main():
    print("=" * 80)
    print("批量升级 Bootstrap 迭代次数到 50000")
    print("=" * 80)
    print()
    
    scripts = find_analyze_scripts()
    print(f"找到 {len(scripts)} 个分析脚本")
    print()
    
    updated_count = 0
    backup_count = 0
    already_updated = 0
    
    for script in scripts:
        project_name = script.parent.parent.name
        print(f"处理: {project_name}")
        
        # 检查是否已经是 50000
        with open(script, 'r', encoding='utf-8') as f:
            if "BOOTSTRAP_SAMPLES = 50000" in f.read():
                print(f"  [OK] 已经是 50000，跳过")
                already_updated += 1
                continue
        
        # 备份
        if backup_results(script):
            print(f"  [OK] 备份结果")
            backup_count += 1
        
        # 更新
        if update_bootstrap_in_script(script):
            print(f"  [OK] 更新到 50000")
            updated_count += 1
        else:
            print(f"  [ERR] 更新失败")
        
        print()
    
    print("=" * 80)
    print("完成!")
    print(f"  已更新: {updated_count}")
    print(f"  已备份: {backup_count}")
    print(f"  已跳过: {already_updated}")
    print()
    print("提示: 脚本已更新，请手动运行各项目的 analyze_interaction.py")
    print("      或修改 batch_update_bootstrap.py 后执行完整流程")

if __name__ == "__main__":
    main()

