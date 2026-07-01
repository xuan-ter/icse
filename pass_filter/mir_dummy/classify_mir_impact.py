import os

def classify_mir_impact():
    base_dir = r'c:\Users\21101\Desktop\实验\mir_dummy'
    input_file = os.path.join(base_dir, 'mir_passes_transform.txt')
    
    out_perf = os.path.join(base_dir, 'mir_passes_impact_performance.txt')
    out_size = os.path.join(base_dir, 'mir_passes_impact_size.txt')

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        if lines and "MIR Transform Passes" in lines[0]:
            passes = lines[1:]
        else:
            passes = lines

    # Define impact sets
    # Many passes impact BOTH, but we classify by PRIMARY INTENT or SIGNIFICANT EFFECT.
    
    # 1. Performance-Critical (Speed)
    # Optimizations that reduce instruction count, improve locality, enable later opts, or reduce runtime overhead.
    perf_keywords = [
        'Inline', 'GVN', 'CopyProp', 'JumpThreading', 
        'InstSimplify', 'SimplifyCfg', # CFG simpl enables everything else
        'ConstProp', 'DataflowConstProp', 
        'SROA', 'ScalarReplacementOfAggregates',
        'ElaborateDrops', # Usually perf (avoids dynamic checks)
        'DestProp', 'DestinationPropagation',
        'LowerIntrinsics', # Essential for backend perf
        'MatchBranchSimplification', # Branch pred
        'RemoveNoopLandingPads', # Exception overhead
        'UnreachablePropagation',
        'EarlyOtherwiseBranch'
    ]

    # 2. Size-Critical (Code Size)
    # Passes that explicitly remove dead code, unused locals, or reduce metadata/stack usage.
    # Note: SimplifyCfg and Inlining also affect size (Inlining increases it, SimplifyCfg decreases it).
    # Here we list ones that are STRONGLY correlated with size reduction or cleanup.
    size_keywords = [
        'DeadStore', 'DSE', 'RemoveZsts', 'RemoveUnneededDrops',
        'SimplifyLocals', 'EraseDerefTemps',
        'UnreachableEnumBranching', # Removes code
        'CleanupPostBorrowck',
        'RemovePlaceMention',
        'PromoteTemps', # Stack size reduction
        'EnumSizeOpt', # Layout/Size
        'SingleUseConsts' # Constant pool size
    ]

    cat_perf = []
    cat_size = []

    for p in passes:
        # Check Perf
        is_perf = False
        if any(k.lower() in p.lower() for k in perf_keywords):
            cat_perf.append(p)
            is_perf = True
        
        # Check Size
        is_size = False
        if any(k.lower() in p.lower() for k in size_keywords):
            cat_size.append(p)
            is_size = True
            
        # Fallback/Overlap handling
        # If not matched by keywords but is a Transform, it likely has minor impact on both.
        # Let's add specific ones that might be missed:
        if not is_perf and not is_size:
            # AbortUnwindingCalls -> Size (removes landing pads/unwind tables)
            if 'AbortUnwindingCalls' in p:
                cat_size.append(p)
            # AddCallGuards -> Security/Correctness (minor perf hit)
            # AddMovesForPackedDrops -> Correctness
            # Derefer -> Cleanup (Size)
            elif 'Derefer' in p:
                cat_size.append(p)
            # PreCodegen -> Final cleanup (Both)
            elif 'PreCodegen' in p:
                cat_perf.append(p)

    # Note: A pass can be in BOTH lists (e.g. SimplifyCfg is good for both).
    # Currently my keyword logic allows overlaps if keywords overlap, but let's ensure
    # some major ones are in both if appropriate.
    
    # Force specific multi-impact passes
    multi_impact = ['SimplifyCfg', 'InstSimplify', 'UnreachablePropagation']
    for p in passes:
        if any(m in p for m in multi_impact):
            if p not in cat_size: cat_size.append(p)
            if p not in cat_perf: cat_perf.append(p)

    # Sort and Deduplicate
    cat_perf = set(cat_perf)
    cat_size = set(cat_size)

    # Identify Dual Impact (Both)
    cat_both = cat_perf.intersection(cat_size)
    
    # Remove Dual Impact from individual lists
    cat_perf = sorted(list(cat_perf - cat_both))
    cat_size = sorted(list(cat_size - cat_both))
    cat_both = sorted(list(cat_both))

    out_both = os.path.join(base_dir, 'mir_passes_impact_both.txt')

    # Write outputs
    def write_list(filepath, name, data):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"{name}\n")
            for item in data:
                f.write(f"{item}\n")
        print(f"Written {len(data)} items to {filepath}")

    write_list(out_perf, "MIR Performance-Only Passes", cat_perf)
    write_list(out_size, "MIR Size-Only Passes", cat_size)
    write_list(out_both, "MIR Performance AND Size (Core) Passes", cat_both)

if __name__ == '__main__':
    classify_mir_impact()
