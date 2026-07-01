"""
综合Pass控制分析工具
功能：全方位分析Pass的控制方式，匹配标准Pass名称、Transform开关及调优参数。
"""
import re
import os

def compare_all_controls():
    passes_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\LLVM_passes_cleaned.txt'
    transforms_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\llvm_args_transform.txt'
    tuning_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\llvm_args_tuning_candidates.txt'
    output_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\pass_control_analysis.txt'
    
    # 1. Load Data
    standard_passes = set()
    with open(passes_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip(): standard_passes.add(line.strip())

    transform_args = set()
    with open(transforms_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('LLVM'): continue
            # Remove -disable- for matching, keep full for display
            clean = line.replace('-disable-', '')
            transform_args.add((clean, line))

    tuning_args = set()
    with open(tuning_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('LLVM'): continue
            tuning_args.add(line)

    # 2. Matching Logic
    results = {} # pass -> {'transforms': [], 'tunings': []}
    
    # Pre-calculate common mappings (Manual Heuristics)
    # These are passes that change names significantly in args
    aliases = {
        'loop-unroll': ['unroll'],
        'loop-vectorize': ['vectorize', 'force-vector'],
        'slp-vectorizer': ['slp'],
        'gvn': ['gvn'],
        'licm': ['licm'],
        'simplifycfg': ['simplifycfg'],
        'inline': ['inline'],
        'loop-rotate': ['rotation'],
        'loop-distribute': ['distribute'],
        'loop-sink': ['sink'],
        'instcombine': ['instcombine']
    }

    for p in sorted(standard_passes):
        results[p] = {'transforms': [], 'tunings': []}
        
        # Define search terms for this pass
        search_terms = [p]
        if p in aliases:
            search_terms.extend(aliases[p])
        
        # Check Transforms
        for clean_arg, full_arg in transform_args:
            # Exact match of cleaned arg
            if clean_arg == p:
                results[p]['transforms'].append(full_arg)
                continue
            
            # Substring match
            # Pass name in arg (e.g. 'licm' in 'machine-licm')
            # Arg name in pass (e.g. 'unroll' in 'loop-unroll')
            for term in search_terms:
                if term in clean_arg or (len(clean_arg) > 3 and clean_arg in term):
                    # Filter weak matches
                    # e.g. "da" in "data..."
                    if len(term) <= 2 and term not in clean_arg.split('-'):
                        continue 
                    results[p]['transforms'].append(full_arg)
                    break # Avoid adding same arg multiple times for different terms

        # Check Tunings
        for arg in tuning_args:
            # Substring match
            for term in search_terms:
                if term in arg:
                    # Filter weak matches
                    # e.g. "da" in "lambda"
                    if len(term) <= 2:
                         # For short terms, require word boundary or start
                         if not (arg.startswith(term + '-') or ('-' + term + '-') in arg):
                             continue
                    
                    results[p]['tunings'].append(arg)
                    break

    # 3. Write Report
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=== Comprehensive LLVM Pass Control Analysis ===\n")
        f.write("Matches Standard Passes against:\n")
        f.write("1. Transform Switches (-disable-*)\n")
        f.write("2. Tuning Parameters (thresholds, limits, costs)\n\n")
        
        # Categories
        fully_controllable = [] # Both
        tuning_only = []
        switch_only = []
        no_control = []

        for p in sorted(standard_passes):
            has_trans = len(results[p]['transforms']) > 0
            has_tune = len(results[p]['tunings']) > 0
            
            if has_trans and has_tune:
                fully_controllable.append(p)
            elif has_tune:
                tuning_only.append(p)
            elif has_trans:
                switch_only.append(p)
            else:
                no_control.append(p)

        f.write(f"Summary:\n")
        f.write(f"- Fully Controllable (Switch + Tuning): {len(fully_controllable)}\n")
        f.write(f"- Tuning Only (Parametric): {len(tuning_only)}\n")
        f.write(f"- Switch Only (On/Off): {len(switch_only)}\n")
        f.write(f"- No Direct Control Found: {len(no_control)}\n")
        f.write("-" * 50 + "\n\n")

        def write_section(title, pass_list):
            f.write(f"### {title} ({len(pass_list)})\n")
            for p in pass_list:
                f.write(f"Pass: [{p}]\n")
                
                trans = results[p]['transforms']
                if trans:
                    f.write(f"  [Switches]:\n")
                    for t in sorted(trans): f.write(f"    {t}\n")
                
                tunes = results[p]['tunings']
                if tunes:
                    f.write(f"  [Tuning Params]:\n")
                    # Limit to top 10 if too many
                    count = 0
                    for t in sorted(tunes):
                        if count >= 10:
                            f.write(f"    ... and {len(tunes)-10} more\n")
                            break
                        f.write(f"    {t}\n")
                        count += 1
                f.write("\n")

        write_section("Fully Controllable (Best for Experimentation)", fully_controllable)
        write_section("Tuning Only (Fine-grained Control)", tuning_only)
        write_section("Switch Only (Coarse-grained Control)", switch_only)
        write_section("No Direct Control Detected", no_control)

    print(f"Analysis complete. Saved to {output_file}")

if __name__ == '__main__':
    compare_all_controls()
