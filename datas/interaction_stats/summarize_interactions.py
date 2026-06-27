import math
import os
from pathlib import Path

import pandas as pd


ROOT = Path(r"d:\MIR_LLVM_NEW")
OUTPUT_DIR = ROOT / "datas" / "interaction_stats"
OUTPUT_CSV = OUTPUT_DIR / "interaction_summary.csv"
OUTPUT_CSV_ZH = OUTPUT_DIR / "interaction_summary_zh.csv"
PREFERRED_RESULT_PATHS = {
    # This analysis directory is generated from:
    # d:\MIR_LLVM_NEW\serde\results_expanded\20260620_123353
    "serde": ROOT / "serde" / "analysis_new" / "did" / "interaction_results.csv",
    # This analysis directory is generated from:
    # d:\MIR_LLVM_NEW\fast_image_resize\results
    "fast_image_resize": ROOT / "fast_image_resize" / "analysis" / "did" / "interaction_results.csv",
    # This analysis directory is generated from:
    # d:\MIR_LLVM_NEW\image\results\run_20260622_162101
    "image": ROOT / "image" / "analysis" / "did" / "interaction_results.csv",
}

ZH_COLUMNS = {
    "project": "项目",
    "source_path": "结果文件路径",
    "analysis_dir": "分析目录",
    "total_pairs": "组合总数",
    "total_positive_delta_count": "总正向delta数量",
    "total_negative_delta_count": "总负向delta数量",
    "zero_count": "零delta数量",
    "independent_count": "独立交互数量",
    "independent_positive_delta_count": "独立交互中的正向delta数量",
    "independent_negative_delta_count": "独立交互中的负向delta数量",
    "highlighted_count": "高亮交互数量",
    "positive_interaction_count": "高亮正交互数量",
    "negative_interaction_count": "高亮负交互数量",
    "highlighted_ratio": "高亮交互占比",
    "sig_mean_abs_delta": "显著交互平均绝对delta",
    "sig_median_abs_delta": "显著交互绝对delta中位数",
    "sig_p95_abs_delta": "显著交互绝对delta的P95",
    "sig_max_abs_delta": "显著交互最大绝对delta",
    "sig_mean_rel_strength": "显著交互平均相对影响强度",
    "top10_abs_delta_share": "前10强交互绝对delta占比",
}


def find_latest_results():
    """
    Pick one current interaction_results.csv per project.
    Prefer analysis_new over analysis, and ignore the top-level shared analysis demos.
    """
    candidates = list(ROOT.glob("*/analysis/did/interaction_results.csv")) + list(
        ROOT.glob("*/analysis_new/did/interaction_results.csv")
    )
    selected = {}

    for path in candidates:
        rel = path.relative_to(ROOT)
        parts = rel.parts
        if len(parts) < 4:
            continue
        project = parts[0]
        analysis_dir = parts[1]
        if project == "analysis":
            continue
        if analysis_dir not in {"analysis", "analysis_new"}:
            continue

        current = selected.get(project)
        if current is None:
            selected[project] = path
            continue

        current_analysis_dir = current.relative_to(ROOT).parts[1]
        if current_analysis_dir == "analysis" and analysis_dir == "analysis_new":
            selected[project] = path
            continue

        if analysis_dir == current_analysis_dir:
            if path.stat().st_mtime > current.stat().st_mtime:
                selected[project] = path

    for project, preferred_path in PREFERRED_RESULT_PATHS.items():
        if preferred_path.exists():
            selected[project] = preferred_path

    return dict(sorted(selected.items()))


def summarize_one(project, csv_path):
    df = pd.read_csv(csv_path)
    total_pairs = int(len(df))

    delta = pd.to_numeric(df.get("delta"), errors="coerce")
    total_positive_delta_count = int((delta > 0).sum())
    total_negative_delta_count = int((delta < 0).sum())
    zero_count = int((delta == 0).sum())

    if "significant" in df.columns:
        significant = df["significant"].fillna(False).astype(bool)
    else:
        significant = pd.Series([False] * len(df))

    if "interaction_type" in df.columns:
        interaction_type = df["interaction_type"].astype(str)
        independent_count = int((interaction_type == "independent").sum())
        positive_interaction_count = int((interaction_type == "positive_interaction").sum())
        negative_interaction_count = int((interaction_type == "negative_interaction").sum())
    else:
        independent_count = int((~significant).sum())
        positive_interaction_count = int((significant & (delta > 0)).sum())
        negative_interaction_count = int((significant & (delta < 0)).sum())

    highlighted_count = positive_interaction_count + negative_interaction_count
    independent_positive_delta_count = int(((~significant) & (delta > 0)).sum())
    independent_negative_delta_count = int(((~significant) & (delta < 0)).sum())
    abs_delta = delta.abs()
    sig_abs_delta = abs_delta[significant & delta.notna()]
    sig_rel_strength = delta[significant & delta.notna()].map(lambda x: abs(math.expm1(float(x))))

    if sig_abs_delta.empty:
        sig_mean_abs_delta = float("nan")
        sig_median_abs_delta = float("nan")
        sig_p95_abs_delta = float("nan")
        sig_max_abs_delta = float("nan")
        sig_mean_rel_strength = float("nan")
    else:
        sig_mean_abs_delta = float(sig_abs_delta.mean())
        sig_median_abs_delta = float(sig_abs_delta.median())
        sig_p95_abs_delta = float(sig_abs_delta.quantile(0.95))
        sig_max_abs_delta = float(sig_abs_delta.max())
        sig_mean_rel_strength = float(sig_rel_strength.mean())

    finite_abs_delta = abs_delta[delta.notna()].sort_values(ascending=False)
    total_abs_delta = float(finite_abs_delta.sum())
    top10_abs_delta_share = (
        float(finite_abs_delta.head(10).sum()) / total_abs_delta if total_abs_delta > 0 else float("nan")
    )

    return {
        "project": project,
        "source_path": str(csv_path),
        "analysis_dir": csv_path.parent.parent.name,
        "total_pairs": total_pairs,
        "total_positive_delta_count": total_positive_delta_count,
        "total_negative_delta_count": total_negative_delta_count,
        "zero_count": zero_count,
        "independent_count": independent_count,
        "independent_positive_delta_count": independent_positive_delta_count,
        "independent_negative_delta_count": independent_negative_delta_count,
        "highlighted_count": highlighted_count,
        "positive_interaction_count": positive_interaction_count,
        "negative_interaction_count": negative_interaction_count,
        "highlighted_ratio": highlighted_count / total_pairs if total_pairs else 0.0,
        "sig_mean_abs_delta": sig_mean_abs_delta,
        "sig_median_abs_delta": sig_median_abs_delta,
        "sig_p95_abs_delta": sig_p95_abs_delta,
        "sig_max_abs_delta": sig_max_abs_delta,
        "sig_mean_rel_strength": sig_mean_rel_strength,
        "top10_abs_delta_share": top10_abs_delta_share,
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    latest = find_latest_results()
    rows = [summarize_one(project, path) for project, path in latest.items()]
    summary_df = pd.DataFrame(rows)
    summary_df.to_csv(OUTPUT_CSV, index=False)
    summary_df.rename(columns=ZH_COLUMNS).to_csv(OUTPUT_CSV_ZH, index=False, encoding="utf-8-sig")
    print(f"Saved summary to {OUTPUT_CSV}")
    print(f"Saved Chinese summary to {OUTPUT_CSV_ZH}")
    if not summary_df.empty:
        print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
