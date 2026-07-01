"""
Pass列表对比工具
功能：对比标准LLVM Pass列表与禁用开关列表，识别可直接控制的Pass和Backend特有Pass。
"""
import re

def compare_pass_lists():
    passes_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\LLVM_passes.txt'
    args_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\llvm_args_transform.txt'
    output_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\llvm_passes_vs_args_comparison.txt'
    
    # 1. Parse LLVM_passes.txt (Standard Pass Names)
    # Format: "pass-name：description" or just "pass-name"
    standard_passes = {}
    with open(passes_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for line in lines:
        line = line.strip()
        if not line or '概述' in line or '变换通道' in line or '分析' in line:
            continue
            
        # Extract pass name (take first part before colon or Chinese characters)
        # Many lines are like "adce：积极消除死代码"
        # Split by fullwidth colon '：' or space
        parts = re.split(r'[：:\s]', line, maxsplit=1)
        pass_name = parts[0].strip()
        
        if pass_name and not pass_name.startswith('print') and not pass_name.startswith('dot-') and not pass_name.startswith('view-'):
            standard_passes[pass_name] = line # Keep full description

    # 2. Parse llvm_args_transform.txt (Disable Switches)
    # Format: "-disable-pass-name"
    disable_switches = set()
    with open(args_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for line in lines:
        line = line.strip()
        if line.startswith('-disable-'):
            # Extract the core name: -disable-licm -> licm
            core_name = line[9:] 
            disable_switches.add(core_name)

    # 3. Compare
    # Intersection: Passes that have a direct disable switch
    # Standard only: Passes that don't have a simple -disable-NAME switch (might be always on, or named differently)
    # Switch only: Switches that disable internal/backend passes not listed in the high-level pass list
    
    intersection = []
    standard_only = []
    switch_only = []
    
    # Check Standard Passes against Switches
    for name in standard_passes:
        if name in disable_switches:
            intersection.append(name)
        else:
            # Fuzzy match attempt? (e.g. loop-unroll vs unroll)
            # For now, strict match
            standard_only.append(name)
            
    # Check Switches against Standard Passes
    for name in disable_switches:
        if name not in standard_passes:
            switch_only.append(name)
            
    intersection.sort()
    standard_only.sort()
    switch_only.sort()

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=== Comparison: LLVM Standard Passes vs Disable Switches ===\n\n")
        
        f.write(f"1. Directly Controllable Passes ({len(intersection)})\n")
        f.write("   (These passes appear in both lists, meaning you can easily disable them via -disable-NAME)\n")
        for name in intersection:
            f.write(f"   - {name}\n")
        f.write("\n")
        
        f.write(f"2. Passes WITHOUT Simple Disable Switch ({len(standard_only)})\n")
        f.write("   (These are standard passes that don't have a direct '-disable-NAME' switch in the probed list.\n")
        f.write("    They might be controllable via other means, or are core passes not meant to be disabled.)\n")
        for name in standard_only:
            f.write(f"   - {name}\n")
        f.write("\n")
        
        f.write(f"3. Backend/Internal Switches NOT in Standard List ({len(switch_only)})\n")
        f.write("   (These are likely backend-specific, low-level, or legacy passes not listed in the high-level summary.\n")
        f.write("    e.g., Hexagon/PPC specific, Machine passes, etc.)\n")
        for name in switch_only:
            f.write(f"   - {name} (-disable-{name})\n")

    print(f"Comparison complete. Found {len(intersection)} matches.")

if __name__ == '__main__':
    compare_pass_lists()
