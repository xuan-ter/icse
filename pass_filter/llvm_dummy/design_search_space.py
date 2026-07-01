"""
搜索空间设计工具
功能：基于验证过的LLVM调优参数，根据参数名称启发式生成推荐的搜索空间（范围、步长）。
"""
import json
import os

def design_search_space():
    base_dir = r'c:\Users\21101\Desktop\实验\llvm_dummy'
    input_file = os.path.join(base_dir, 'llvm_args_tuning_valid.txt')
    output_file = os.path.join(base_dir, 'tuning_search_space.json')
    
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        if lines and "Valid LLVM Tuning Arguments" in lines[0]:
            valid_args = lines[1:]
        else:
            valid_args = lines

    # Heuristic Rules for Search Space
    # We define categories of parameters and assign search ranges.
    
    search_space = {}

    for arg in valid_args:
        lower_arg = arg.lower()
        
        # 1. Thresholds (Costs/Limits)
        if 'threshold' in lower_arg:
            # Inline thresholds are typically higher (hundreds)
            if 'inline' in lower_arg:
                 # Default usually ~225
                 search_space[arg] = [50, 150, 225, 325, 500, 1000]
            # Loop unroll thresholds (cost)
            elif 'unroll' in lower_arg:
                 # Default ~150
                 search_space[arg] = [50, 100, 150, 300, 500]
            # Vectorizer thresholds
            elif 'vector' in lower_arg or 'slp' in lower_arg:
                 search_space[arg] = [0, 10, 50, 100] # Often lower costs
            # Generic thresholds
            else:
                 search_space[arg] = [10, 50, 100, 200, 500]

        # 2. Counts / Depths / Limits
        elif 'count' in lower_arg or 'limit' in lower_arg or 'depth' in lower_arg or 'max' in lower_arg:
            # Small integers (recursion depth, unroll count)
            if 'unroll' in lower_arg:
                search_space[arg] = [2, 4, 8, 16, 32]
            elif 'depth' in lower_arg:
                search_space[arg] = [2, 4, 8, 16, 32]
            elif 'recursion' in lower_arg:
                search_space[arg] = [2, 4, 8, 16]
            # Larger limits (instruction counts)
            elif 'inst' in lower_arg or 'size' in lower_arg:
                search_space[arg] = [100, 500, 1000, 5000]
            else:
                search_space[arg] = [2, 5, 10, 20, 50]

        # 3. Probabilities / Weights (often 0-100 or 0-1000)
        elif 'prob' in lower_arg or 'weight' in lower_arg:
            search_space[arg] = [0, 25, 50, 75, 90, 100]

        # 4. Factors (Multipliers)
        elif 'factor' in lower_arg:
            search_space[arg] = [1, 2, 4, 8, 16]
            
        # 5. Levels (Optimization levels)
        elif 'level' in lower_arg:
            search_space[arg] = [0, 1, 2, 3]

        # 6. Costs
        elif 'cost' in lower_arg:
             search_space[arg] = [0, 1, 2, 5, 10, 50]
             
        # Fallback for unknown numeric types
        else:
            # Conservative small integers
            search_space[arg] = [0, 1, 2, 4, 8, 16]

    # Special Overrides for well-known parameters (if present)
    overrides = {
        'inline-threshold': [75, 225, 325, 500, 800],
        'unroll-count': [0, 2, 4, 8, 16], # 0 usually means auto
        'unroll-threshold': [100, 150, 300, 600],
        'loop-unswitch-threshold': [50, 100, 200],
        'slp-threshold': [-10, 0, 10, 20], # Negative sometimes forces it
        'vectorizer-maximize-bandwidth': [0, 1], # Boolean-like
    }
    
    for k, v in overrides.items():
        # Only override if the arg actually exists in valid_args
        # We need to match partial names if exact match fails? 
        # No, exact match is safer for now.
        if k in search_space:
            search_space[k] = v

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(search_space, f, indent=4)
        
    print(f"Designed search space for {len(search_space)} parameters.")

if __name__ == '__main__':
    design_search_space()
