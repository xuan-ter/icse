
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(r"d:\MIR_LLVM_NEW")

def calculate_required_bootstrap(n_tests, alpha=0.05, min_effect_size=0.01):
    """
    计算所需的 bootstrap 迭代次数
    n_tests: 检验数量（用于 BH 校正）
    alpha: 显著性水平
    min_effect_size: 最小效应大小（用于估计 p 值精度要求）
    """
    # BH 校正需要的最小 p 值（第一个显著）
    required_p_threshold = alpha / n_tests
    
    # 最小可检测的 p 值约为 1/(n_bootstrap + 1)
    # 我们希望有足够的精度来检测 p <= required_p_threshold
    # 安全系数设为 10 倍
    required_bootstrap = max(
        int(10 / required_p_threshold),  # 基于 p 值精度
        2000,  # 最小保底
        int(n_tests * 10)  # 与检验数量成正比
    )
    return required_bootstrap, required_p_threshold

def analyze_project_results():
    """分析各个项目的特征"""
    summary_df = pd.read_csv(ROOT / "datas" / "interaction_stats" / "interaction_summary.csv")
    
    print("=" * 80)
    print("真实项目 Bootstrap 需求分析")
    print("=" * 80)
    print()
    
    results = []
    for _, row in summary_df.iterrows():
        project = row['project']
        n_pairs = row['total_pairs']
        sig_count = row['highlighted_count']
        sig_ratio = row['highlighted_ratio']
        max_delta = row.get('sig_max_abs_delta', np.nan)
        
        # 计算理论所需 bootstrap
        req_bootstrap, req_p_thresh = calculate_required_bootstrap(n_pairs)
        
        # 评估当前是否足够
        current_bootstrap = 2000  # 从之前的分析中得知
        current_p_min = 1 / (current_bootstrap + 1)
        is_sufficient = current_p_min <= req_p_thresh
        
        results.append({
            'project': project,
            'n_pairs': n_pairs,
            'sig_count': sig_count,
            'sig_ratio': sig_ratio,
            'max_delta': max_delta,
            'required_p_threshold': req_p_thresh,
            'min_p_with_2000': current_p_min,
            'required_bootstrap': req_bootstrap,
            'current_sufficient': is_sufficient
        })
    
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('required_bootstrap', ascending=False)
    
    print("项目 Bootstrap 需求评估表")
    print("-" * 100)
    print(results_df.to_string(index=False, float_format=lambda x: f"{x:.6f}"))
    print()
    
    print("=" * 80)
    print("关键发现")
    print("=" * 80)
    print()
    print(f"1. 所有项目都进行 {n_pairs} 次统计检验")
    print(f"2. BH 校正要求第一个显著的 p 值 ≤ {0.05/n_pairs:.8f}")
    print(f"3. 当前使用 2000 次 bootstrap，最小可检测 p 值 ≈ 0.0005")
    print()
    
    insufficient = results_df[~results_df['current_sufficient']]
    if len(insufficient) > 0:
        print(f"4. 以下项目当前 bootstrap 可能不足（需要更精确的 p 值）：")
        for _, row in insufficient.iterrows():
            print(f"   - {row['project']}: 需要 ~{row['required_bootstrap']} 次")
    print()
    
    # 推荐方案
    print("=" * 80)
    print("Bootstrap 迭代次数推荐方案")
    print("=" * 80)
    print()
    print("方案 1: 快速探索 (2000 次)")
    print("  - 适用: 效应大的项目（如 regex, trait_test, aho-corasick）")
    print("  - 优点: 计算快")
    print("  - 缺点: 可能漏掉小效应但稳定的交互")
    print()
    print("方案 2: 标准分析 (10000 次)")
    print("  - 适用: 大多数项目")
    print("  - 优点: 在精度和速度间较好平衡")
    print()
    print("方案 3: 精确分析 (50000+ 次)")
    print("  - 适用: 所有项目，特别是效应较小的（如 rustls, hyper, bat）")
    print("  - 优点: 能检测到更精细的显著交互")
    print()
    print("方案 4: 自适应策略（推荐）")
    print("  - 先运行 2000 次初步筛选")
    print("  - 对置信区间接近不跨零的交互（CI 包含 0 但接近边界）")
    print("  - 单独对这些交互运行更多 bootstrap (50000-100000 次)")
    print()
    
    return results_df

def plot_bootstrap_tradeoff():
    """绘制 bootstrap 次数与可检测 p 值的关系"""
    n_tests = 1660
    bootstrap_range = np.logspace(3, 6, 100)  # 1000 到 1,000,000
    min_p_values = 1 / (bootstrap_range + 1)
    bh_threshold = 0.05 / n_tests
    
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(bootstrap_range, min_p_values, 'b-', linewidth=2, label='最小可检测 p 值')
    ax.axhline(y=bh_threshold, color='r', linestyle='--', label=f'BH 校正阈值 ({bh_threshold:.6f})')
    ax.axvline(x=2000, color='g', linestyle=':', label='当前使用 (2000)')
    ax.axvline(x=10000, color='orange', linestyle=':', label='推荐标准 (10000)')
    ax.axvline(x=50000, color='purple', linestyle=':', label='推荐精确 (50000)')
    
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlabel('Bootstrap 迭代次数 (对数刻度)')
    ax.set_ylabel('最小可检测 p 值 (对数刻度)')
    ax.set_title('Bootstrap 迭代次数与 p 值检测能力的关系')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(ROOT / "datas" / "interaction_stats" / "bootstrap_tradeoff.png", dpi=300)
    print(f"图表已保存到: {ROOT / 'datas' / 'interaction_stats' / 'bootstrap_tradeoff.png'}")
    return fig

if __name__ == "__main__":
    results_df = analyze_project_results()
    plot_bootstrap_tradeoff()
    
    print()
    print("=" * 80)
    print("最终建议")
    print("=" * 80)
    print()
    print("基于对所有真实项目的分析，建议如下：")
    print()
    print("1. 对于新项目，默认使用 10000-50000 次 bootstrap")
    print("2. 如果计算资源有限，至少使用 10000 次")
    print("3. 对于 rustls 这种效应较小但稳定的项目，使用 50000+ 次")
    print("4. 对于已经用 2000 次发现大量显著交互的项目（如 regex, aho-corasick）")
    print("   可以保持 2000 次，但如需完整分析建议升级到 10000 次")
    print()

