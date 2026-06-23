import pandas as pd
import os

# 读取原始实验数据
data_path = r'd:\MIR_LLVM_NEW\tokio\results\20260608_201933\experiment_results.csv'
df = pd.read_csv(data_path)

# 为每个ConfigName提取对应的MIR_Pass和LLVM_Pass
config_mapping = df.groupby('ConfigName').agg({
    'MIR_Pass': 'first',
    'LLVM_Pass': 'first'
}).reset_index()

# 保存映射表
mapping_path = r'd:\MIR_LLVM_NEW\tokio\analysis\config_to_pass_mapping.csv'
config_mapping.to_csv(mapping_path, index=False)
print(f"ConfigName to pass mapping saved to {mapping_path}")
print("\nFirst few entries:")
print(config_mapping.head(20))

# 读取summary_medians数据并合并
summary_path = r'd:\MIR_LLVM_NEW\tokio\results\20260608_201933\summary_medians.csv'
summary_df = pd.read_csv(summary_path)
print(f"\nsummary_medians.csv has {len(summary_df)} entries")
print(summary_df.head())
