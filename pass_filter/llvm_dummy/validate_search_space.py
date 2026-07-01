"""
搜索空间验证工具
功能：验证JSON定义的搜索空间中的所有参数和开关是否能被当前Rustc编译器接受。
"""
import json
import subprocess
import os
import sys

def validate_parameter(param_name, test_value):
    # Construct the argument
    # Note: llvm-args expects arguments as they would appear on command line
    # e.g. -inline-threshold=100
    llvm_arg = f"-{param_name}={test_value}"
    
    cmd = [
        "rustc",
        "-C", f"llvm-args={llvm_arg}",
        "dummy.rs",
        "--emit=metadata"
    ]
    
    try:
        # Run rustc and capture output
        # We don't want to see the output unless it fails, but even then we just want to know result
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        return result.returncode == 0
    except Exception as e:
        print(f"Error running rustc: {e}")
        return False

def validate_search_space(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    validated_data = {
        "description": "Validated LLVM Tuning Search Space",
        "passes": {}
    }
    
    total_params = 0
    valid_params = 0
    
    print(f"Validating parameters from {input_file}...")
    
    for pass_name, config in data.get("passes", {}).items():
        valid_pass_params = {}
        
        # Check params
        for param, range_info in config.get("parameters", {}).items():
            total_params += 1
            # Test with the default or min value
            test_val = range_info.get("default", 0)
            
            if validate_parameter(param, test_val):
                valid_pass_params[param] = range_info
                valid_params += 1
                # print(f"  [OK] {param}")
            else:
                print(f"  [FAIL] {param} (rejected by rustc)")
        
        # Check switches (boolean flags)
        # We don't need to validate switches as much if they came from help-hidden, 
        # but let's do it if we can.
        # Switches in the JSON are just names like "-disable-..."
        # We can test them by passing them directly.
        valid_switches = []
        for switch in config.get("switches", []):
            # Switch already has leading dash usually?
            # In pass_control_analysis.txt it says "-disable-..."
            # So we pass it as is.
            
            # Remove leading dash for the check if it's double dashed?
            # No, llvm-args takes whatever.
            
            # Wait, validate_parameter adds a dash. 
            # If switch is "-disable-foo", we should pass "-disable-foo" not "--disable-foo".
            # My validate_parameter adds a dash.
            
            # Let's manually handle switches
            test_arg = switch
            cmd = ["rustc", "-C", f"llvm-args={test_arg}", "dummy.rs", "--emit=metadata"]
            res = subprocess.run(cmd, capture_output=True, check=False)
            if res.returncode == 0:
                valid_switches.append(switch)
            else:
                print(f"  [FAIL Switch] {switch}")

        if valid_pass_params or valid_switches:
            validated_data["passes"][pass_name] = {
                "switches": valid_switches,
                "parameters": valid_pass_params
            }
            
    print(f"\nValidation complete.")
    print(f"Total Parameters: {total_params}")
    print(f"Valid Parameters: {valid_params}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(validated_data, f, indent=2)

if __name__ == "__main__":
    base_dir = r"c:\Users\21101\Desktop\实验\llvm_dummy"
    input_json = os.path.join(base_dir, "llvm_search_space.json")
    output_json = os.path.join(base_dir, "llvm_search_space_validated.json")
    
    # Ensure dummy.rs exists
    if not os.path.exists(os.path.join(base_dir, "dummy.rs")):
        with open(os.path.join(base_dir, "dummy.rs"), 'w') as f:
            f.write("fn main() {}")
            
    validate_search_space(input_json, output_json)
