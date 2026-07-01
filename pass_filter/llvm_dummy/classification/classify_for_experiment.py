"""
实验矩阵专用分类工具 (7类)
分类标准：Vectorization, Loop, ControlFlow, Memory, DataFlow, CodeGen, Pipeline/Profile/LTO

Changes based on feedback:
1. -disable-vp -> Pipeline/Profile/LTO (Value Profiling)
2. -disable-expand-reductions -> Vectorization (Reduction expansion)
3. -disable-cfi-fixup -> Pipeline/Profile/LTO (CFI/Metadata)
4. -disable-demotion -> DataFlow (SSA demotion)
5. -disable-nounwind-inference -> Pipeline/Profile/LTO (Attribute inference)
6. -disable-icp -> DataFlow (Interprocedural Constant Propagation)
7. -disable-complex-addr-modes -> CodeGen (Address mode selection)
8. -disable-gep-const-evaluation -> DataFlow (Constant eval)
"""
import os

def classify_for_experiment():
    base_dir = r'c:\Users\21101\Desktop\实验\llvm_dummy\classification'
    input_file = os.path.join(base_dir, 'llvm_args_generic_only.txt')
    output_file = os.path.join(base_dir, 'llvm_args_categorized_7_classes.txt')
    
    if not os.path.exists(input_file):
        print(f"Input file not found: {input_file}")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        args = [line.strip() for line in f.readlines() if line.strip()]

    # Categories
    categories = {
        'Vectorization': [],
        'Loop': [],
        'ControlFlow': [],
        'Memory': [],
        'DataFlow': [],
        'Pipeline/Profile/LTO': [],
        'CodeGen': []
    }

    # Explicit mappings for specific args (Priority 1)
    explicit_map = {
        '-disable-vp': 'Pipeline/Profile/LTO',
        '-disable-expand-reductions': 'Vectorization',
        '-disable-cfi-fixup': 'Pipeline/Profile/LTO',
        '-disable-demotion': 'DataFlow',
        '-disable-nounwind-inference': 'Pipeline/Profile/LTO',
        '-disable-icp': 'DataFlow',
        '-disable-complex-addr-modes': 'CodeGen',
        '-disable-gep-const-evaluation': 'DataFlow',
        # Adding more based on feedback logic
        '-disable-preheader-prot': 'Loop', # Preheader usually loop related
    }

    # Keyword mappings (Priority 2)
    # Order matters! More specific categories should be checked first if using if-elif
    
    for arg in args:
        lower = arg.lower()
        
        # 1. Check explicit map first
        if arg in explicit_map:
            categories[explicit_map[arg]].append(arg)
            continue
            
        # 2. Pipeline/Profile/LTO (Global, Link-time, Profile, Debug, Bitcode, Attributes)
        if any(x in lower for x in ['lto', 'profile', 'pgo', 'sample', 'debug', 'bitcode', 'global', 'whole-program', 'cgdata', 'last-run-tracking', 'ondemand-mds', 'atexit', 'inference']):
            categories['Pipeline/Profile/LTO'].append(arg)
            
        # 3. Vectorization (Vector, SLP, Interleaved, VP-intrinsics but not VP-profiling)
        elif any(x in lower for x in ['vector', 'slp', 'interleaved', 'binop-extract-shuffle', 'vec-lib']):
            categories['Vectorization'].append(arg)
            
        # 4. Loop (Loop, LICM, LSR, LFTR, IV, Peeling)
        elif any(x in lower for x in ['loop', 'licm', 'lsr', 'lftr', 'iv-', 'indvar', 'peeling']):
            categories['Loop'].append(arg)
            
        # 5. Memory (Load, Store, Mem, GEP, Promote, SROA, Alias)
        elif any(x in lower for x in ['load', 'store', 'mem', 'gep', 'promote', 'sroa', 'alias', 'dse', 'const-offset', 'ext-ld']):
            categories['Memory'].append(arg)
            
        # 6. ControlFlow (Branch, Block, IfCvt, Tail, Jump, CFG, Unwind, CFI)
        elif any(x in lower for x in ['branch', 'block', 'ifcvt', 'tail', 'jump', 'cfg', 'unwind', 'gotol', 'chr', 'preheader']):
            categories['ControlFlow'].append(arg)
            
        # 7. DataFlow (CSE, DCE, CopyProp, Constant, Combine, Phi, Cleanups, Reassociate, SSC)
        elif any(x in lower for x in ['cse', 'dce', 'copyprop', 'const', 'combine', 'phi', 'cleanups', 'reassociate', 'ssc', 'sink', 'hoist', 'inline', 'redundant', 'mergeicmps', 'select-optimize', 'copy-opt', 'type-promotion']):
            categories['DataFlow'].append(arg)
            
        # 8. CodeGen (Machine, Sched, RegAlloc, RA, Spill, Peephole, Expand, Lowering, CGP, 2addr)
        # Everything else usually falls here or specific CodeGen terms
        elif any(x in lower for x in ['machine', 'sched', 'regalloc', 'ra-', 'post-ra', 'spill', 'peephole', 'expand', 'lower', 'cgp', '2addr', 'dwarf', 'prolog', 'epilog', 'isel', 'fixup', 'hack', 'strictnode', 'addr-modes']):
            categories['CodeGen'].append(arg)
            
        else:
            # Fallback
            categories['CodeGen'].append(arg)

    # Sort within categories
    for cat in categories:
        categories[cat].sort()

    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        for cat, items in categories.items():
            f.write(f"=== {cat} ({len(items)}) ===\n")
            for item in items:
                f.write(f"{item}\n")
            f.write("\n")

    print(f"Categorized {len(args)} arguments into {output_file}")
    for cat, items in categories.items():
        print(f"  {cat}: {len(items)}")

if __name__ == '__main__':
    classify_for_experiment()
