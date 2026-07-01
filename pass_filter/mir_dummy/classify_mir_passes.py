import os

def classify_mir_passes():
    base_dir = r'c:\Users\21101\Desktop\实验\mir_dummy'
    input_file = os.path.join(base_dir, 'mir_passes_valid_switches.txt')
    
    output_analysis = os.path.join(base_dir, 'mir_passes_analysis.txt')
    output_transform = os.path.join(base_dir, 'mir_passes_transform.txt')

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        # Skip header if present
        if lines and "Valid MIR passes" in lines[0]:
            passes = lines[1:]
        else:
            passes = lines

    # Categories
    cat_analysis = []
    cat_transform = []

    # Keywords that strongly suggest Analysis
    # Note: In Rust MIR context, most toggleable passes are transforms.
    # But we look for explicit analysis naming.
    analysis_keywords = [
        'analysis',
        'check',
        'verify',
        'dump',
        'lint',
        'validator'
    ]

    for p in passes:
        lower_p = p.lower()
        
        # Check for Analysis
        if any(k in lower_p for k in analysis_keywords):
            # Special case: "PostAnalysisNormalize" is a transform (normalization)
            if 'normalize' in lower_p:
                cat_transform.append(p)
            # Special case: "DataflowConstProp" is a transform (propagation)
            elif 'prop' in lower_p:
                cat_transform.append(p)
            else:
                cat_analysis.append(p)
        else:
            # Default to Transform
            cat_transform.append(p)

    # Write outputs
    def write_list(filepath, name, data):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"{name}\n")
            for item in sorted(data):
                f.write(f"{item}\n")
        print(f"Written {len(data)} items to {filepath}")

    write_list(output_analysis, "MIR Analysis Passes", cat_analysis)
    write_list(output_transform, "MIR Transform Passes", cat_transform)

if __name__ == '__main__':
    classify_mir_passes()
