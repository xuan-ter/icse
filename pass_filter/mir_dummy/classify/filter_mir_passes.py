import os
import re

# Define input and output paths
base_dir = r"c:\Users\21101\Desktop\实验\mir_dummy"
input_file = os.path.join(base_dir, "mir_passes_transform.txt")
output_dir = os.path.join(base_dir, "classify")
tunable_output = os.path.join(output_dir, "mir_tunable_optimizations.txt")
excluded_output = os.path.join(output_dir, "mir_excluded_lowering_cleanup.txt")

# Define classification rules
lowering_passes = {
    "ElaborateDrops", "ElaborateBoxDerefs", "LowerIntrinsics", "PromoteTemps",
    "CleanupPostBorrowck", "AddMovesForPackedDrops", "PreCodegen",
    "LowerSliceLenCalls", "EraseDerefTemps", "PostAnalysisNormalize",
    "Subtyper", "StateTransform", "Deaggregator", "AddRetag"
}

safety_passes = {
    "AddCallGuards", "AbortUnwindingCalls"
}

cleanup_passes = {
    "SimplifyCfg-initial", "SimplifyCfg-promote-consts", "SimplifyCfg-pre-optimizations",
    "SimplifyCfg-after-unreachable-enum-branching", "SimplifyCfg-final",
    "SimplifyLocals-before-const-prop", "SimplifyLocals-after-value-numbering", "SimplifyLocals-final",
    "RemoveZsts", "RemoveNoopLandingPads", "RemoveUnneededDrops",
    "RemovePlaceMention", "Derefer",
    "SimplifyConstCondition-after-const-prop", "SimplifyConstCondition-after-inst-simplify", "SimplifyConstCondition-final",
    "SimplifyComparisonIntegral"
}

optimization_passes = {
    "Inline", "ForceInline",
    "CopyProp", "DataflowConstProp", "DestinationPropagation", "ReferencePropagation",
    "ScalarReplacementOfAggregates",
    "DeadStoreElimination-initial", "DeadStoreElimination-final", "UnreachablePropagation",
    "JumpThreading", "MatchBranchSimplification", "EarlyOtherwiseBranch", "UnreachableEnumBranching",
    "GVN",
    "InstSimplify-after-simplifycfg", "InstSimplify-before-inline",
    "EnumSizeOpt", "ImpossiblePredicates",
    "SingleUseConsts"
}

def classify_pass(pass_name):
    # Remove any leading/trailing whitespace
    clean_name = pass_name.strip()
    
    if clean_name in lowering_passes:
        return "Lowering (Keep)", clean_name
    if clean_name in safety_passes:
        return "Safety (Keep)", clean_name
    if clean_name in cleanup_passes:
        return "Cleanup (Recommended Keep)", clean_name
    if clean_name in optimization_passes:
        return "Tunable Optimization", clean_name
        
    return "Unknown/Other", clean_name

def main():
    if not os.path.exists(input_file):
        print(f"Error: Input file not found at {input_file}")
        return

    tunable_list = []
    excluded_list = []
    
    print(f"Reading from: {input_file}")

    with open(input_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            
            # Debug first few lines
            if i < 5:
                print(f"Line {i}: {repr(line)}")

            # Try to split by arrow or just take the text after the first non-digit/arrow chars
            # Regex: Match optional digits, optional arrow/spaces, then the name
            # Pattern: ^(\d+)?\s*[→->]?\s*(.+)$
            match = re.search(r'(?:[\d]+\s*[→\->]\s*)?(.+)', line)
            if not match:
                print(f"Skipping unparseable line: {line}")
                continue
                
            name_part = match.group(1).strip()
            
            if name_part == "MIR Transform Passes":
                continue

            category, clean_name = classify_pass(name_part)
            
            # Filter out "Unknown" if it looks like a header or garbage
            if category == "Unknown/Other" and "Passes" in clean_name:
                continue
                
            entry = f"{clean_name:<50} | {category}"
            
            if category == "Tunable Optimization":
                tunable_list.append(entry)
            else:
                excluded_list.append(entry)

    # Write outputs
    with open(tunable_output, 'w', encoding='utf-8') as f:
        f.write("MIR Tunable Optimizations (Suitable for Experiments)\n")
        f.write("====================================================\n")
        f.write(f"{'Pass Name':<50} | Category\n")
        f.write("-" * 70 + "\n")
        for item in tunable_list:
            f.write(item + "\n")
            
    with open(excluded_output, 'w', encoding='utf-8') as f:
        f.write("MIR Excluded Passes (Lowering/Safety/Cleanup - Recommend Default)\n")
        f.write("=================================================================\n")
        f.write(f"{'Pass Name':<50} | Category\n")
        f.write("-" * 70 + "\n")
        for item in excluded_list:
            f.write(item + "\n")

    print(f"Classification complete.")
    print(f"Tunable optimizations: {len(tunable_list)} (Saved to {tunable_output})")
    print(f"Excluded passes: {len(excluded_list)} (Saved to {excluded_output})")

if __name__ == "__main__":
    main()
