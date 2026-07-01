"""
功能分类工具
功能：基于Pass的功能特性（如循环、向量化、内存等）对LLVM参数进行分类。
"""
import os

def classify_functional():
    base_dir = r'c:\Users\21101\Desktop\实验\llvm_dummy\classification'
    input_file = os.path.join(base_dir, 'llvm_args_by_target.txt')
    
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        return

    # Read only the Generic section
    generic_args = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reading_generic = False
        for line in f:
            line = line.strip()
            if "=== Generic" in line:
                reading_generic = True
                continue
            if "===" in line and reading_generic: # Next section
                break
            if reading_generic and line:
                generic_args.append(line)

    categories = {
        'Vectorization': ['vec', 'slp'],
        'Loop': ['loop', 'licm', 'lsr', 'lftr', 'indvar', 'iv-users', 'cycle'],
        'Inlining': ['inline'],
        'Control Flow': ['branch', 'block', 'tail', 'jump', 'switch', 'cfg', 'ifcvt', 'sink', 'hoist', 'placement', 'demotion', 'goto'],
        'Data Flow/Simplification': ['cse', 'dce', 'copy', 'const', 'instcombine', 'simplify', 'combine', 'redundant', 'elim'],
        'Memory': ['memcpy', 'memmove', 'load', 'store', 'gep', 'sroa', 'dse', 'memop', 'stack', 'aa', 'alias'],
        'CodeGen/Backend': ['sched', 'reg', 'alloc', 'peephole', 'layout', 'ra-', 'post-ra', 'spill', 'packetizer', 'fixup', 'gisel'],
        'Debug/Metadata': ['debug', 'dwarf', 'symbol', 'verify', 'print', 'view', 'dot-'],
    }

    classified = {k: [] for k in categories.keys()}
    others = []

    for arg in generic_args:
        lower_arg = arg.lower()
        matched = False
        
        # Check specific categories first
        for cat, keywords in categories.items():
            if any(k in lower_arg for k in keywords):
                classified[cat].append(arg)
                matched = True
                break
        
        if not matched:
            others.append(arg)

    # Write output
    output_file = os.path.join(base_dir, 'llvm_args_functional.txt')
    with open(output_file, 'w', encoding='utf-8') as f:
        for cat, args in classified.items():
            if args:
                f.write(f"=== {cat} ===\n")
                for arg in sorted(args):
                    f.write(f"{arg}\n")
                f.write("\n")
        
        f.write("=== Others (Unclassified) ===\n")
        for arg in sorted(others):
            f.write(f"{arg}\n")

    print(f"Functional Classification Complete.")
    for k, v in classified.items():
        print(f"  - {k}: {len(v)}")
    print(f"  - Others: {len(others)}")

if __name__ == '__main__':
    classify_functional()
