"""
调优参数发现工具
功能：从llvm-help.txt中挖掘潜在的数值型调优参数（如threshold, limit, cost等），排除无关选项。
"""
import re
import os

def discovery_tuning_args():
    input_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\llvm-help.txt'
    output_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\llvm_args_tuning_candidates.txt'
    
    # 1. Keywords to search for (Numeric/Strategy knobs)
    # We want things that are NOT just enable/disable.
    target_keywords = [
        'threshold', 'limit', 'count', 'depth', 'cost', 'level', 
        'max', 'min', 'factor', 'width', 'size', 'probability'
    ]
    
    # 2. Terms to exclude (Debug/Internal/Printer)
    exclude_keywords = [
        'debug', 'print', 'dump', 'verify', 'trace', 'stats', 'time',
        'check', 'remark', 'warn', 'error', 'assert', 'diag', 'help'
    ]

    candidates = []

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line.startswith('-'):
            continue
            
        # Parse the argument name
        # Line format: --arg-name=<type>  - Description
        parts = line.split(maxsplit=1)
        arg_part = parts[0]
        
        # We look for arguments that explicitly show they take a value
        # e.g., <uint>, <int>, <n>, <value>
        has_value_indicator = any(x in arg_part for x in ['<uint>', '<int>', '<n>', '<value>', '<string>'])
        
        if not has_value_indicator:
            continue

        # Extract arg name (remove leading -- and value part)
        # e.g., --inline-threshold=<int> -> inline-threshold
        arg_name_clean = arg_part.lstrip('-').split('=')[0]
        
        # Check exclusion
        if any(ex in arg_name_clean.lower() for ex in exclude_keywords):
            continue
            
        # Check inclusion (must contain at least one target keyword OR be clearly a parameter)
        # Actually, if it takes <int>/<uint>, it's almost certainly a tuning parameter.
        # But let's filter to keep the list relevant to "Optimization Tuning".
        if any(tk in arg_name_clean.lower() for tk in target_keywords):
             candidates.append(arg_name_clean)

    # Deduplicate and sort
    candidates = sorted(list(set(candidates)))

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("LLVM Tuning Candidates (Numeric/Enum)\n")
        for c in candidates:
            f.write(f"{c}\n")
    
    print(f"Found {len(candidates)} tuning candidates.")

if __name__ == '__main__':
    discovery_tuning_args()
