import json
import csv

# 读取原始 JSON 数据
with open(r'd:\MIR_LLVM_NEW\table\table_json\combined_experiment_matrix.json', 'r') as f:
    data = json.load(f)

combinations = data['combinations']

mir_passes = []
llvm_toggles = []

for combo in combinations:
    mir = combo.get('mir')
    llvm = combo.get('llvm')
    
    # 收集 MIR passes
    if mir and mir.get('pass') not in ('All', None):
        pass_name = mir['pass']
        switches = mir['switches']
        if pass_name not in [p['Name'] for p in mir_passes]:
            mir_passes.append({
                'Index': None,
                'Type': 'MIR',
                'Name': pass_name,
                'Switch': switches[0] if switches else None,
                'Description': f'MIR Optimization Pass: {pass_name}'
            })
    
    # 收集 LLVM toggles
    if llvm and llvm.get('pass') not in ('All', 'baseline', None):
        pass_name = llvm['pass']
        switches = llvm['switches']
        if pass_name not in [p['Name'] for p in llvm_toggles]:
            llvm_toggles.append({
                'Index': None,
                'Type': 'LLVM',
                'Name': pass_name,
                'Switch': switches[0] if switches else None,
                'Description': f'LLVM Optimization Toggle: {pass_name}'
            })

# 排序并添加编号
mir_passes = sorted(mir_passes, key=lambda x: x['Name'])
for i, p in enumerate(mir_passes, 1):
    p['Index'] = f'MIR_{i:02d}'

llvm_toggles = sorted(llvm_toggles, key=lambda x: x['Name'])
for i, p in enumerate(llvm_toggles, 1):
    p['Index'] = f'LLVM_{i:02d}'

# 合并成完整清单
full_list = mir_passes + llvm_toggles

# 写入 CSV
csv_path = r'd:\MIR_LLVM_NEW\pass_filter\optimization_inventory\optimization_factors.csv'
with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
    fieldnames = ['Index', 'Type', 'Name', 'Switch', 'Description']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for item in full_list:
        writer.writerow(item)

print(f'Generated inventory at: {csv_path}')
print(f'MIR passes: {len(mir_passes)}')
print(f'LLVM toggles: {len(llvm_toggles)}')
