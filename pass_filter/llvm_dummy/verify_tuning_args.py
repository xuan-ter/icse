"""
调优参数验证器
功能：验证候选调优参数是否接受数值输入，确认其作为调优旋钮的有效性。
"""
import subprocess
import os
import sys

def verify_tuning_args():
    base_dir = r'c:\Users\21101\Desktop\实验\llvm_dummy'
    input_file = os.path.join(base_dir, 'llvm_args_tuning_candidates.txt')
    output_valid = os.path.join(base_dir, 'llvm_args_tuning_valid.txt')
    
    # Create a minimal test file
    test_rs = os.path.join(base_dir, 'test_tuning.rs')
    if not os.path.exists(test_rs):
        with open(test_rs, 'w', encoding='utf-8') as f:
            f.write('fn main() { println!("test"); }\n')

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        if lines and "LLVM Tuning Candidates" in lines[0]:
            args = lines[1:]
        else:
            args = lines

    valid_args = []
    
    print(f"Testing {len(args)} candidates...")
    
    for i, arg in enumerate(args):
        # Construct command
        # We try to pass a dummy value '1' (or '10') to see if it accepts it.
        # If the argument expects an enum (string), '1' might fail or be rejected, 
        # but the error message will tell us it's "unknown argument" vs "invalid value".
        # If it's "Unknown command line argument", then it's not valid for this rustc.
        
        # Note: Some args might need specific values.
        # But here we mainly filter out "Unknown command line argument".
        
        # We use a value of '1' for most numeric args.
        test_val = '1'
        
        cmd = f'rustc "{test_rs}" --crate-type bin -C llvm-args="-{arg}={test_val}" -o test_dummy.exe'
        
        try:
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                text=True,
                encoding='utf-8' # Ensure encoding handles output correctly
            )
            
            stderr = result.stderr
            
            # Check for "Unknown command line argument"
            if "Unknown command line argument" in stderr:
                # print(f"Invalid: {arg}")
                pass
            # Check for "Option 'x' requires a value" (shouldn't happen as we provided one)
            elif "requires a value" in stderr:
                 # This means it IS a valid option but we formatted it wrong? 
                 # But we used -arg=val.
                 pass
            else:
                # If compilation succeeded or failed with a different error (e.g. invalid value),
                # it means the ARGUMENT NAME is recognized.
                # If it failed with "invalid value '1'", it's still a VALID tuning knob, just needs better values.
                
                # Let's be stricter: If it compiles (returncode 0), it's definitely valid.
                if result.returncode == 0:
                    valid_args.append(arg)
                    # print(f"Valid (Accepted): {arg}")
                elif "invalid value" in stderr or "not a valid" in stderr:
                    # It recognized the arg but rejected '1'. This is good! It means the knob exists.
                    valid_args.append(arg)
                    # print(f"Valid (Value Error): {arg}")
                else:
                    # Some other error?
                    pass
                    
        except Exception as e:
            print(f"Error testing {arg}: {e}")

        if (i + 1) % 50 == 0:
            print(f"Progress: {i + 1}/{len(args)}")

    # Cleanup
    if os.path.exists('test_dummy.exe'):
        os.remove('test_dummy.exe')
    if os.path.exists('test_dummy.pdb'):
        os.remove('test_dummy.pdb')

    # Write results
    with open(output_valid, 'w', encoding='utf-8') as f:
        f.write("Valid LLVM Tuning Arguments\n")
        for arg in valid_args:
            f.write(f"{arg}\n")
            
    print(f"Found {len(valid_args)} valid tuning arguments out of {len(args)} candidates.")

if __name__ == '__main__':
    verify_tuning_args()
