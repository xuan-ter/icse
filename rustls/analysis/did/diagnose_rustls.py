
import pandas as pd
import numpy as np

# Read the interaction results
df = pd.read_csv("interaction_results.csv")

print("=" * 60)
print("RUSTLS 交互分析诊断")
print("=" * 60)

print("\n1. 基本统计")
print(f"总交互对数量: {len(df)}")
print(f"significant 列值数量: {df['significant'].sum()}")

print("\n2. 原始 p 值分布")
print("原始 p 值统计:")
print(df['p_value'].describe())

print("\n最小原始 p 值:")
print(df['p_value'].nsmallest(10))

print("\n3. BH 调整后的 p 值分布")
print("调整后 p 值统计:")
print(df['p_adj'].describe())

print("\n最小调整后 p 值:")
print(df['p_adj'].nsmallest(10))

print("\n4. 前20个最小 p 值的情况:")
top20 = df.nsmallest(20, 'p_value')[['mir_pass', 'llvm_pass', 'delta', 'p_value', 'p_adj', 'ci_low', 'ci_high', 'significant']]
print(top20)

print("\n5. BH 调整计算:")
print(f"BH 调整公式: p_adj = min(1, p_value * n / rank)")
print(f"其中 n = {len(df)}")
print("对于最小 p 值的调整过程:")

p_values = df['p_value'].sort_values().values
n = len(p_values)

for i, p in enumerate(p_values[:10]):
    rank = i + 1
    adj = p * n / rank
    print(f"  第 {rank} 小的原始 p 值: {p:.6f} → 调整后: {min(1, adj):.6f}")

print("\n6. 置信区间是否跨零的情况:")
ci_cross_zero = (df['ci_low'] <= 0) & (df['ci_high'] >= 0)
ci_not_cross_zero = ~ci_cross_zero
print(f"置信区间跨零: {ci_cross_zero.sum()}")
print(f"置信区间不跨零: {ci_not_cross_zero.sum()}")
print("\n在置信区间不跨零的交互中:")
no_cross = df[ci_not_cross_zero]
print(f"  p_adj < 0.05: {(no_cross['p_adj'] < 0.05).sum()}")
print(f"  p_adj >= 0.05: {(no_cross['p_adj'] >= 0.05).sum()}")

if len(no_cross) > 0:
    print("\n置信区间不跨零的交互中最小的 5 个 p_adj:")
    print(no_cross.nsmallest(5, 'p_adj')[['mir_pass', 'llvm_pass', 'delta', 'p_value', 'p_adj', 'ci_low', 'ci_high']])

