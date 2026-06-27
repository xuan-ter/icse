
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(r"d:\MIR_LLVM_NEW")

def find_analyze_scripts():
    """查找所有 analyze_interaction.py 脚本"""
    scripts = []
    # 使用 glob 查找
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
    
    # 匹配 BOOTSTRAP_SAMPLES = 数字
    pattern = fr"BOOTSTRAP_SAMPLES\s*=\s*{old_value}"
    replacement = f"BOOTSTRAP_SAMPLES = {new_value}"
    
    if re.search(pattern, content):
        new_content = re.sub(pattern, replacement, content)
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"✓ 更新: {script_path.relative_to(ROOT)}")
        return True
    else:
        print(f"⚠ 未找到匹配项: {script_path.relative_to(ROOT)}")
        return False

def backup_results(script_path):
    """备份 2000 次的结果"""
    script_dir = script_path.parent
    results_file = script_dir / "interaction_results.csv"
    backup_file = script_dir / "interaction_results_2000.csv"
    
    if results_file.exists() and not backup_file.exists():
        import shutil
        shutil.copy2(results_file, backup_file)
        print(f"  备份结果: {backup_file.name}")
        return True
    elif backup_file.exists():
        print(f"  备份已存在: {backup_file.name}")
        return True
    return False

def run_analysis(script_path):
    """运行分析脚本"""
    print(f"  运行分析...")
    try:
        result = subprocess.run(
            ['python', str(script_path)],
            cwd=str(script_path.parent),
            capture_output=True,
            text=True,
            timeout=3600  # 1小时超时
        )
        if result.returncode == 0:
            print(f"  ✓ 分析完成")
            return True
        else:
            print(f"  ✗ 分析失败，退出码: {result.returncode}")
            print(f"    错误: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"  ✗ 运行出错: {e}")
        return False

def main():
    print("=" * 80)
    print("批量升级 Bootstrap 迭代次数到 50000")
    print("=" * 80)
    print()
    
    scripts = find_analyze_scripts()
    print(f"找到 {len(scripts)} 个分析脚本")
    print()
    
    # 先确认要更新哪些脚本
    print("即将更新的脚本:")
    for i, script in enumerate(scripts, 1):
        print(f"  {i}. {script.relative_to(ROOT)}")
    print()
    
    # 确认
    response = input("确认要继续吗？(y/n): ")
    if response.lower() != 'y':
        print("操作已取消")
        return
    
    print()
    print("开始处理...")
    print()
    
    success_count = 0
    skip_count = 0
    
    for i, script in enumerate(scripts, 1):
        print(f"[{i}/{len(scripts)}] {script.parent.parent.name}")
        
        # 1. 备份结果
        backup_results(script)
        
        # 2. 更新脚本
        if update_bootstrap_in_script(script):
            # 3. 运行分析
            if run_analysis(script):
                success_count += 1
            else:
                skip_count += 1
        else:
            skip_count += 1
        
        print()
    
    print("=" * 80)
    print("完成!")
    print(f"  成功: {success_count}")
    print(f"  跳过/失败: {skip_count}")
    print()
    print("下一步: 运行 summarize_interactions.py 更新汇总表")

if __name__ == "__main__":
    main()

