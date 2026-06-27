
import numpy as np

print("="*80)
print("BH 多重比较校正原理解释")
print("="*80)

# rustls 的情况
n_tests = 1660
alpha = 0.05

print(f"\n1. 检验数量: {n_tests}")
print(f"2. 显著性水平: {alpha}")
print(f"3. 如果不进行校正，预期的假阳性数: {n_tests * alpha:.1f}")

print("\n4. BH 校正步骤（简化版）:")
print("   a. 将所有 p 值从小到大排序")
print("   b. 对于第 k 个 p 值，计算临界值: k/n * alpha")
print("   c. 找到最大的 k 使得 p_k &lt;= k/n * alpha")
print("   d. 只有前 k 个 p 值被认为是显著的")

print("\n5. rustls 的最小原始 p 值: 0.001")
print(f"   对于第一个 p 值 (k=1):")
print(f"     临界值 = (1/1660) * 0.05 = {0.05/1660:.8f}")
print(f"     0.001 &gt; {0.05/1660:.8f} → 不满足显著条件")

print(f"\n6. 计算 rustls 需要的最小原始 p 值才能达到显著:")
print(f"   对于第一个位置，需要 p &lt;= (1/1660)*0.05 ≈ {0.05/1660:.8f}")
print(f"   这需要约 {1/(0.05/1660):.0f} 次 bootstrap 迭代")
print(f"   当前只有 2000 次迭代，这就是为什么 p 值只能降到 0.001")

print("\n" + "="*80)
print("另一种理解方式：")
print("="*80)
print("\n在 2000 次 bootstrap 中：")
print("- 最小可能的 p 值是 1/(2000+1) ≈ 0.0005")
print("- 但我们看到的最小 p 值是 0.001")
print("- 这意味着在 2000 次 bootstrap 中，有 2 次或更少的结果能达到极端值")
print("\n这在统计学上不够强，尤其是需要同时做 1660 次检验时！")
