"""
Pass与Transform开关对比工具
功能：对比标准Pass与Transform参数，通过精确和模糊匹配识别Pass对应的禁用开关。
"""
import re

def compare_passes_and_transforms():
    passes_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\LLVM_passes_cleaned.txt'
    transforms_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\llvm_args_transform.txt'
    output_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\pass_vs_transform_comparison.txt'
    
    # 1. Load Standard Passes
    standard_passes = set()
    with open(passes_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                standard_passes.add(line)
                
    # 2. Load Transform Args
    transform_args = set()
    # Map cleaned name back to full arg for display
    arg_map = {} 
    
    with open(transforms_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('LLVM'): continue
            
            # Remove -disable- prefix for matching
            clean_arg = line
            if line.startswith('-disable-'):
                clean_arg = line[len('-disable-'):]
            
            transform_args.add(clean_arg)
            arg_map[clean_arg] = line

    # 3. Comparison Logic
    exact_matches = []
    fuzzy_matches = {}
    no_match_passes = []
    
    # Check passes against args
    for p in sorted(standard_passes):
        if p in transform_args:
            exact_matches.append((p, arg_map[p]))
        else:
            # Try fuzzy matching
            # Check if pass name is contained in arg or arg in pass name
            # e.g. "licm" matches "machine-licm"
            # e.g. "loop-unroll" matches "loop-unroll-and-jam"? (maybe not strict equal)
            
            current_fuzzies = []
            for arg in transform_args:
                # 1. Pass is substring of Arg (e.g. licm -> machine-licm)
                # 2. Arg is substring of Pass (e.g. unroll -> loop-unroll)
                # 3. Handle acronyms? (lsr = loop strength reduction -> loop-reduce?)
                
                if p in arg:
                    current_fuzzies.append(arg_map[arg])
                elif arg in p and len(arg) > 3: # Avoid matching short args like "p10"
                    current_fuzzies.append(arg_map[arg])
            
            # Special case for LSR (Loop Reduce)
            if p == 'loop-reduce' and 'lsr' in transform_args:
                current_fuzzies.append(arg_map['lsr'])
                
            if current_fuzzies:
                fuzzy_matches[p] = sorted(current_fuzzies)
            else:
                no_match_passes.append(p)

    # 4. Write Report
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=== LLVM Pass vs Transform Switch Comparison ===\n")
        f.write(f"Total Standard Passes: {len(standard_passes)}\n")
        f.write(f"Total Transform Switches: {len(transform_args)}\n\n")
        
        f.write(f"--- 1. Exact Matches ({len(exact_matches)}) ---\n")
        f.write("(Pass Name matches switch suffix exactly)\n")
        for p, arg in exact_matches:
            f.write(f"{p:<30} -> {arg}\n")
            
        f.write(f"\n--- 2. Fuzzy/Related Matches ({len(fuzzy_matches)}) ---\n")
        f.write("(Pass Name is part of switch name or vice versa)\n")
        for p in sorted(fuzzy_matches.keys()):
            f.write(f"Pass: {p}\n")
            for arg in fuzzy_matches[p]:
                f.write(f"  -> {arg}\n")
            f.write("\n")
            
        f.write(f"--- 3. Passes with NO Direct Control Switch ({len(no_match_passes)}) ---\n")
        f.write("(These might be analysis passes, mandatory passes, or named differently)\n")
        for p in sorted(no_match_passes):
            f.write(f"{p}\n")

    print(f"Comparison complete. Saved to {output_file}")

if __name__ == '__main__':
    compare_passes_and_transforms()
