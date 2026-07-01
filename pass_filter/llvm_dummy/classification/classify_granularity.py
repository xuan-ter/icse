"""
粒度分类工具
功能：按作用域粒度（Module, CGSCC, Function, Loop）对Transform参数进行分类。
"""
import os

def classify_by_granularity():
    base_dir = r'c:\Users\21101\Desktop\实验\llvm_dummy\classification'
    input_file = os.path.join(base_dir, 'llvm_args_transform.txt')
    
    # Output files
    out_module = os.path.join(base_dir, 'llvm_args_transform_module.txt')
    out_cgscc = os.path.join(base_dir, 'llvm_args_transform_cgscc.txt')
    out_function = os.path.join(base_dir, 'llvm_args_transform_function.txt')
    out_loop = os.path.join(base_dir, 'llvm_args_transform_loop.txt')

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        # Skip header if present
        if lines and "LLVM Transform Args" in lines[0]:
            args = lines[1:]
        else:
            args = lines

    # Categories
    cat_module = []
    cat_cgscc = []
    cat_function = []
    cat_loop = []

    # Heuristic Rules
    for arg in args:
        lower_arg = arg.lower()
        
        # 1. Loop (Specific keywords)
        # Includes machine loops (hwloops) and IR loops (licm, lsr, lftr, indvars)
        if any(x in lower_arg for x in ['loop', 'licm', 'lftr', 'lsr', 'indvar', 'iv-users', 'cycle']):
            cat_loop.append(arg)
            continue

        # 2. Module (Global scope keywords)
        # Includes LTO, Global, Merge, IPO, WholeProgram
        if any(x in lower_arg for x in ['module', 'global', 'lto', 'whole-program', 'merge', 'cgdata', 'bitcode', 'cross-dso', 'funcattrs']):
            # funcattrs is technically CGSCC usually, but thinlto-funcattrs is module/summary
            if 'thinlto-funcattrs' in lower_arg:
                 cat_module.append(arg)
            else:
                 # Standard merge-functions etc.
                 cat_module.append(arg)
            continue

        # 3. CGSCC (Call Graph)
        # Inline is the big one.
        if any(x in lower_arg for x in ['inline', 'cgscc', 'argpromotion']):
             # Partial inlining can be module, but fits CGSCC/CallGraph context well enough for "granularity"
             cat_cgscc.append(arg)
             continue

        # 4. Function (Default)
        # Includes most scalar optimizations, vectorization (SLP), and almost all Backend/MachineFunction passes
        # (e.g., peephole, isel, scheduling, regalloc - though regalloc isn't usually disabled via simple flags like this)
        cat_function.append(arg)

    # Write outputs
    def write_list(filepath, name, data):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"{name}\n")
            for item in sorted(data):
                f.write(f"{item}\n")
        print(f"Written {len(data)} items to {filepath}")

    write_list(out_module, "Module Level", cat_module)
    write_list(out_cgscc, "CGSCC Level", cat_cgscc)
    write_list(out_function, "Function Level", cat_function)
    write_list(out_loop, "Loop Level", cat_loop)

if __name__ == '__main__':
    classify_by_granularity()
