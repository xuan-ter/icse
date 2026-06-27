
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# 加载两次分析的结果
df_2000 = pd.read_csv("interaction_results_2000.csv")
df_50000 = pd.read_csv("interaction_results.csv")

print("=" * 80)
print("Bootstrap 迭代次数对比分析")
print("=" * 80)

print("\n1. p 值对比")
print("-" * 80)
print(f"2000 次: 最小 p值 = {df_2000['p_value'].min():.6f}, 最大 p值 = {df_2000['p_value'].max():.6f}")
print(f"50000次: 最小 p值 = {df_50000['p_value'].min():.6f}, 最大 p值 = {df_50000['p_value'].max():.6f}")

# 取 top 交互做详细对比
top_idx = df_2000['abs_delta'].idxmax()
top_mir = df_2000.loc[top_idx, 'mir_pass']
top_llvm = df_2000.loc[top_idx, 'llvm_pass']

print(f"\n2. 最强交互 ({top_mir} + {top_llvm}) 详细对比:")
print("-" * 80)
row_2000 = df_2000[(df_2000['mir_pass'] == top_mir) & (df_2000['llvm_pass'] == top_llvm)].iloc[0]
row_50000 = df_50000[(df_50000['mir_pass'] == top_mir) & (df_50000['llvm_pass'] == top_llvm)].iloc[0]

print(f"{'指标':<20} {'2000次':<15} {'50000次':<15}")
print(f"{'-'*20} {'-'*15} {'-'*15}")
print(f"{'delta':<20} {row_2000['delta']:<15.6f} {row_50000['delta']:<15.6f}")
print(f"{'CI 下界':<20} {row_2000['ci_low']:<15.6f} {row_50000['ci_low']:<15.6f}")
print(f"{'CI 上界':<20} {row_2000['ci_high']:<15.6f} {row_50000['ci_high']:<15.6f}")
print(f"{'CI 宽度':<20} {row_2000['ci_high']-row_2000['ci_low']:<15.6f} {row_50000['ci_high']-row_50000['ci_low']:<15.6f}")
print(f"{'原始 p值':<20} {row_2000['p_value']:<15.6f} {row_50000['p_value']:<15.6f}")
print(f"{'调整 p值':<20} {row_2000['p_adj']:<15.6f} {row_50000['p_adj']:<15.6f}")
print(f"{'显著':<20} {str(row_2000['significant']):<15} {str(row_50000['significant']):<15}")

# 可视化对比
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# 1. p 值分布对比
ax = axes[0, 0]
ax.hist(df_2000['p_value'], bins=50, alpha=0.5, label='2000 次', density=True)
ax.hist(df_50000['p_value'], bins=50, alpha=0.5, label='50000 次', density=True)
ax.set_xlabel('p 值')
ax.set_ylabel('密度')
ax.set_title('p 值分布对比')
ax.legend()
ax.axvline(0.05, color='red', linestyle='--', alpha=0.7, label='p=0.05')

# 2. 调整后 p 值分布对比
ax = axes[0, 1]
ax.hist(df_2000['p_adj'], bins=50, alpha=0.5, label='2000 次', density=True)
ax.hist(df_50000['p_adj'], bins=50, alpha=0.5, label='50000 次', density=True)
ax.set_xlabel('调整后 p 值')
ax.set_ylabel('密度')
ax.set_title('BH 调整后 p 值分布对比')
ax.legend()
ax.axvline(0.05, color='red', linestyle='--', alpha=0.7, label='p=0.05')

# 3. top 20 p 值对比
ax = axes[1, 0]
top_20_2000 = df_2000.nsmallest(20, 'p_value')
top_20_50000 = df_50000.nsmallest(20, 'p_value')
x = np.arange(20)
width = 0.35
ax.bar(x - width/2, top_20_2000['p_value'], width, label='2000 次')
ax.bar(x + width/2, top_20_50000['p_value'], width, label='50000 次')
ax.set_xlabel('排名')
ax.set_ylabel('p 值')
ax.set_title('Top 20 最小 p 值对比')
ax.legend()
ax.set_yscale('log')
ax.axvline(0.05, color='red', linestyle='--', alpha=0.7)

# 4. 显著交互数量对比
ax = axes[1, 1]
sizes = [df_2000['significant'].sum(), df_50000['significant'].sum()]
labels = ['2000 次', '50000 次']
ax.bar(labels, sizes, color=['#ff9999', '#66b3ff'])
ax.set_ylabel('显著交互数量')
ax.set_title('显著交互数量对比')
for i, v in enumerate(sizes):
    ax.text(i, v + 2, str(v), ha='center', va='bottom')

plt.tight_layout()
plt.savefig('bootstrap_comparison.png', dpi=300)
plt.savefig('bootstrap_comparison.pdf')
print("\n可视化结果已保存到 bootstrap_comparison.png/pdf")

# 模拟展示 bootstrap 分辨率如何影响 p 值
print("\n" + "=" * 80)
print("3. Bootstrap 分辨率解释")
print("=" * 80)
print("\n对于 n 次 bootstrap：")
print(f"  - 最小可检测 p 值 ≈ 1/(n+1)")
print(f"  - 2000次: 最小 p值 ≈ 1/2001 ≈ 0.0005")
print(f"  - 50000次: 最小 p值 ≈ 1/50001 ≈ 0.00002")
print("\n为什么这很重要？")
print("  - p 值计算方式: p = 2 * min( (boot_delta>=0)+1, (boot_delta<=0)+1 ) / (n+1)")
print("  - 如果真实效应很强，在 50000 次中几乎所有 bootstrap 结果都在同一侧")
print("  - 这使得 p 值可以非常小，足以通过 BH 多重比较校正")
print("\nBH 校正需要什么？")
print("  - 对于 1660 次检验，第一个显著需要 p <= 0.05/1660 ≈ 0.00003")
print("  - 2000次 bootstrap 无法达到这么小的 p 值（受限于分辨率）")
print("  - 50000次 bootstrap 可以达到这个精度！")
