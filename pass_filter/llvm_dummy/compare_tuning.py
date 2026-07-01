"""
Pass与调优参数对比工具
功能：分析标准Pass与其相关的数值型调优参数（如阈值、限制、计数等）。
"""
import re

def compare_pass_vs_tuning():
    passes_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\LLVM_passes.txt'
    tuning_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\llvm_args_tuning_valid.txt'
    output_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\llvm_passes_vs_tuning_comparison.txt'
    
    # 1. Parse Standard Passes
    standard_passes = {}
    with open(passes_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for line in lines:
        line = line.strip()
        if not line or '概述' in line or '变换通道' in line or '分析' in line:
            continue
        parts = re.split(r'[：:\s]', line, maxsplit=1)
        pass_name = parts[0].strip()
        if pass_name and not pass_name.startswith('print') and not pass_name.startswith('dot-') and not pass_name.startswith('view-'):
            standard_passes[pass_name] = line

    # 2. Parse Tuning Arguments
    tuning_args = []
    with open(tuning_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for line in lines:
        line = line.strip()
        if line and not line.startswith('Valid'):
            tuning_args.append(line)
            
    # 3. Fuzzy Match
    # We try to see if a pass name appears inside a tuning argument
    # e.g., pass "inline" -> tuning "inline-threshold"
    
    matches = {} # Pass Name -> List of related tuning args
    unmatched_passes = []
    
    for p_name in standard_passes:
        # Heuristic: split pass name by '-' and see if major parts exist in tuning arg
        # But simpler: just check if pass name is a substring of tuning arg
        # e.g. "licm" in "licm-max-num-fp-reassociations"
        
        related = []
        for t_arg in tuning_args:
            if p_name in t_arg:
                # Basic substring match
                related.append(t_arg)
            else:
                # Try handling "loop-unroll" vs "unroll-threshold"
                # If pass name has multiple parts, check if the "core" part matches
                if '-' in p_name:
                    core_parts = p_name.split('-')
                    # Try matching the last part or significant parts?
                    # "loop-unroll" -> "unroll"
                    if len(core_parts) > 1 and core_parts[-1] in t_arg:
                        # But be careful: "loop" is too generic.
                        if len(core_parts[-1]) > 3: # Ignore 'da', 'aa'
                            # Check if t_arg also contains 'threshold' or 'limit' etc.
                            # This might be too loose.
                            pass
                            
        if related:
            matches[p_name] = related
        else:
            unmatched_passes.append(p_name)
            
    # Refined matching logic for specific known cases
    # loop-unroll -> unroll-threshold
    special_mappings = {
        'loop-unroll': ['unroll-threshold', 'unroll-count'],
        'inline': ['inline-threshold'],
        'simplifycfg': ['simplifycfg-branch-fold-threshold'],
        'licm': ['licm-max-num-uses-traversed'],
        'slp-vectorizer': ['slp-threshold'] # if pass is named slp-vectorizer? (not in list, usually just slp?)
    }
    
    # 4. Write Output
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=== Comparison: LLVM Standard Passes vs Tuning Arguments ===\n\n")
        
        f.write(f"1. Tunable Passes ({len(matches)})\n")
        f.write("   (Standard Passes that have at least one related tuning argument)\n")
        
        sorted_matches = sorted(matches.keys())
        for p_name in sorted_matches:
            f.write(f"   [Pass: {p_name}]\n")
            # Sort tuning args by length/similarity? Just alpha
            for t in sorted(matches[p_name]):
                f.write(f"     -> {t}\n")
            f.write("\n")
            
        f.write(f"2. Passes without Obvious Tuning Knobs ({len(unmatched_passes)})\n")
        f.write("   (No tuning argument found containing the pass name directly)\n")
        for p_name in sorted(unmatched_passes):
            f.write(f"   - {p_name}\n")

    print(f"Comparison complete. Found {len(matches)} tunable passes.")

if __name__ == '__main__':
    compare_pass_vs_tuning()
