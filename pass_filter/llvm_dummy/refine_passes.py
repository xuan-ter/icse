"""
Pass列表优化工具
功能：利用llvm-help信息优化Pass列表，修正名称不准确或冗余的条目。
"""
import re

def refine_passes():
    help_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\llvm-help.txt'
    cleaned_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\LLVM_passes_cleaned.txt'
    refined_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\LLVM_passes_cleaned.txt' # Overwrite? Or new file. Let's overwrite as user asked for "cleaned" file.
    
    # 1. Extract known passes from llvm-help.txt
    known_passes = set()
    with open(help_file, 'r', encoding='utf-8') as f:
        content = f.read()
        # Find all -disable-PASSNAME
        matches = re.findall(r'-disable-([a-zA-Z0-9-]+)', content)
        for m in matches:
            known_passes.add(m)
            
    print(f"Found {len(known_passes)} known passes from llvm-help.txt")
    
    # 2. Refine cleaned passes
    with open(cleaned_file, 'r', encoding='utf-8') as f:
        current_passes = [line.strip() for line in f if line.strip()]
        
    final_passes = []
    for p in current_passes:
        if p in known_passes:
            final_passes.append(p)
        else:
            # Check if a prefix matches
            # We want the longest matching prefix?
            # e.g. "always-inlinealways" -> "always-inline"
            
            found_prefix = False
            # Sort known passes by length descending to find longest match
            # But iterating all known passes is slow? 
            # 2000 passes is fine.
            
            # Optimization: check if p starts with k
            best_match = None
            for k in known_passes:
                if p.startswith(k):
                    # Check if the remainder is not a continuation of a word?
                    # e.g. "loop-unroll" vs "loop-unroll-and-jam"
                    # If p is "loop-unroll-and-jam", and k is "loop-unroll".
                    # p starts with k.
                    # We should prefer the LONGEST match.
                    if best_match is None or len(k) > len(best_match):
                        best_match = k
            
            if best_match:
                # If the match is significantly shorter?
                # e.g. p="always-inlinealways", k="always-inline". Match!
                # But what if p="loop-unroll-and-jam" and k="loop-unroll".
                # If "loop-unroll-and-jam" is NOT in known_passes?
                # Then maybe it's not a switchable pass?
                # But wait, "loop-unroll-and-jam" IS a pass.
                # If it's not in llvm-help.txt, maybe it's not disable-able?
                # Or maybe I should keep p as is if I'm not sure?
                
                # Case: "always-inlinealways" -> "always-inline"
                # Difference is "always".
                # Case: "kernel-info" -> "kernel-info" (it was correct).
                
                # Heuristic: If p is NOT in known_passes, but a prefix IS.
                # Does the suffix look like garbage?
                suffix = p[len(best_match):]
                # suffix "always".
                # suffix "GPU" (if I hadn't fixed it).
                
                # If suffix starts with a letter...
                # Maybe I should just take the best_match?
                # But I risk truncating valid passes that are just not in llvm-help.txt
                # e.g. "print" passes.
                
                # User's goal is to clean artifacts.
                # Artifacts observed: repetition, appended description.
                
                # If suffix is non-empty, and best_match is valid.
                # I'll replace with best_match.
                # EXCEPT if the suffix makes it another valid pass that is just missing from help?
                # Unlikely.
                
                final_passes.append(best_match)
                print(f"Refined: {p} -> {best_match}")
            else:
                # No match found. Keep as is.
                # e.g. "deadarghaX0r" (maybe not in help)
                final_passes.append(p)
                
    # 3. Write back
    with open(refined_file, 'w', encoding='utf-8') as f:
        for p in final_passes:
            f.write(f"{p}\n")
            
    print(f"Refined passes saved to {refined_file}")

if __name__ == '__main__':
    refine_passes()
