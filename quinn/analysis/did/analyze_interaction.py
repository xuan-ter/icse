import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "results"))
OUTPUT_DIR = BASE_DIR
BOOTSTRAP_SAMPLES = 50000
BOOTSTRAP_SEED = 42
os.makedirs(OUTPUT_DIR, exist_ok=True)


def find_latest_results_dir():
    candidates = []
    if not os.path.isdir(RESULTS_ROOT):
        raise FileNotFoundError(f"Results directory not found: {RESULTS_ROOT}")

    for entry in os.scandir(RESULTS_ROOT):
        if not entry.is_dir():
            continue
        csv_path = os.path.join(entry.path, "experiment_results.csv")
        if os.path.exists(csv_path):
            candidates.append(entry.path)

    if not candidates:
        raise FileNotFoundError(f"No experiment_results.csv found under {RESULTS_ROOT}")

    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[0]


DATA_DIR = find_latest_results_dir()
RAW_CSV = os.path.join(DATA_DIR, "experiment_results.csv")


def normalize_pass_names(df):
    """
    Normalize baseline spellings so the all-off baseline becomes (None, None).
    """

    def clean_name(name):
        if pd.isna(name):
            return "None"
        s = str(name).strip()
        if s.lower() in {"none", "baseline", "nan", "", "n/a", "na", "all"}:
            return "None"
        return s

    df = df.copy()
    df["LLVM_Pass"] = df["LLVM_Pass"].apply(clean_name)
    df["MIR_Pass"] = df["MIR_Pass"].apply(clean_name)
    return df


def load_raw_experiment_data():
    """
    Load repeated raw runs and keep only successful, positive-runtime samples.
    """
    raw_df = pd.read_csv(RAW_CSV)
    if "Status" in raw_df.columns:
        raw_df = raw_df[raw_df["Status"].astype(str).str.strip().str.lower() == "success"].copy()
    raw_df["TotalRuntime(s)"] = pd.to_numeric(raw_df["TotalRuntime(s)"], errors="coerce")
    raw_df = raw_df[raw_df["TotalRuntime(s)"] > 0].copy()
    raw_df = normalize_pass_names(raw_df)
    print(f"Loaded {len(raw_df)} raw runs from {RAW_CSV}.")
    return raw_df


def build_samples_lookup(df, metric):
    grouped = (
        df[["MIR_Pass", "LLVM_Pass", metric]]
        .dropna(subset=["MIR_Pass", "LLVM_Pass", metric])
        .groupby(["MIR_Pass", "LLVM_Pass"])[metric]
    )
    return {
        (mir, llvm): values.to_numpy(dtype=float)
        for (mir, llvm), values in grouped
    }


def _bootstrap_mean(values, n_bootstrap, rng):
    idx = rng.integers(0, len(values), size=(n_bootstrap, len(values)))
    return values[idx].mean(axis=1)


def bootstrap_interaction(z00, z10, z01, z11, n_bootstrap, seed):
    """
    Bootstrap the DiD delta on log-runtime samples.
    """
    rng = np.random.default_rng(seed)
    boot00 = _bootstrap_mean(z00, n_bootstrap, rng)
    boot10 = _bootstrap_mean(z10, n_bootstrap, rng)
    boot01 = _bootstrap_mean(z01, n_bootstrap, rng)
    boot11 = _bootstrap_mean(z11, n_bootstrap, rng)
    boot_delta = (boot01 - boot11) - (boot00 - boot10)

    point_delta = float((z01.mean() - z11.mean()) - (z00.mean() - z10.mean()))
    ci_low, ci_high = np.percentile(boot_delta, [2.5, 97.5])
    p_nonneg = (np.sum(boot_delta >= 0.0) + 1.0) / (len(boot_delta) + 1.0)
    p_nonpos = (np.sum(boot_delta <= 0.0) + 1.0) / (len(boot_delta) + 1.0)
    p_value = min(1.0, 2.0 * min(p_nonneg, p_nonpos))

    return {
        "delta": point_delta,
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
        "p_value": float(p_value),
    }


def benjamini_hochberg(p_values):
    """
    Benjamini-Hochberg FDR adjustment.
    """
    p = np.asarray(p_values, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order]
    adjusted = np.empty(n, dtype=float)
    prev = 1.0
    for i in range(n - 1, -1, -1):
        rank = i + 1
        value = min(prev, ranked[i] * n / rank)
        adjusted[i] = value
        prev = value
    out = np.empty(n, dtype=float)
    out[order] = np.clip(adjusted, 0.0, 1.0)
    return out


def classify_effect_strength(results_df):
    """
    Classify interactions using the current BH-adjusted p + CI significance rule.
    """
    results_df = results_df.copy()
    results_df["abs_delta"] = results_df["delta"].abs()
    results_df["interaction_rank"] = results_df["abs_delta"].rank(method="dense", ascending=False).astype(int)

    strong_threshold = float(results_df["abs_delta"].quantile(0.95))
    extreme_threshold = float(results_df["abs_delta"].quantile(0.99))

    results_df["effect_level"] = "weak"
    results_df.loc[results_df["abs_delta"] >= strong_threshold, "effect_level"] = "strong"
    results_df.loc[results_df["abs_delta"] >= extreme_threshold, "effect_level"] = "extreme"
    results_df.loc[
        (results_df["abs_delta"] < strong_threshold)
        & (results_df["abs_delta"] >= float(results_df["abs_delta"].median())),
        "effect_level",
    ] = "moderate"

    results_df["p_adj"] = benjamini_hochberg(results_df["p_value"].to_numpy(dtype=float))
    results_df["significant"] = ((results_df["ci_low"] > 0.0) | (results_df["ci_high"] < 0.0)) & (
        results_df["p_adj"] < 0.05
    )
    results_df["crosses_zero"] = ~results_df["significant"]
    results_df["interaction_type"] = "independent"
    results_df.loc[results_df["significant"] & (results_df["delta"] < 0), "interaction_type"] = (
        "negative_interaction"
    )
    results_df.loc[results_df["significant"] & (results_df["delta"] > 0), "interaction_type"] = (
        "positive_interaction"
    )

    summary = {
        "strong_threshold": strong_threshold,
        "extreme_threshold": extreme_threshold,
        "highlighted_count": int(results_df["significant"].sum()),
        "negative_highlighted_count": int(((results_df["significant"]) & (results_df["delta"] < 0)).sum()),
        "positive_highlighted_count": int(((results_df["significant"]) & (results_df["delta"] > 0)).sum()),
    }
    return results_df, summary


def analyze_interactions(raw_df, metric="TotalRuntime(s)", n_bootstrap=BOOTSTRAP_SAMPLES, seed=BOOTSTRAP_SEED):
    """
    Run full DiD analysis directly on repeated raw runs.
    """
    samples_lookup = build_samples_lookup(raw_df, metric)
    y00 = samples_lookup.get(("None", "None"))
    if y00 is None or len(y00) == 0:
        print("WARNING: No baseline (y00) raw runs found.")
        return None

    mir_passes = sorted({p for p, _ in samples_lookup.keys() if p not in ["None", "All"]})
    llvm_passes = sorted({l for _, l in samples_lookup.keys() if l not in ["None", "All"]})
    print(f"Found {len(mir_passes)} MIR passes and {len(llvm_passes)} LLVM passes.")

    z00 = np.log(y00)
    y00_geo = float(np.exp(z00.mean()))
    print(f"Baseline (y00) geometric mean: {y00_geo:.4f}")

    results = []
    for mir_pass in mir_passes:
        for llvm_pass in llvm_passes:
            y10 = samples_lookup.get((mir_pass, "None"))
            y01 = samples_lookup.get(("None", llvm_pass))
            y11 = samples_lookup.get((mir_pass, llvm_pass))
            if y10 is None or y01 is None or y11 is None:
                continue

            z10 = np.log(y10)
            z01 = np.log(y01)
            z11 = np.log(y11)
            boot = bootstrap_interaction(
                z00,
                z10,
                z01,
                z11,
                n_bootstrap=n_bootstrap,
                seed=seed + len(results),
            )

            y10_geo = float(np.exp(z10.mean()))
            y01_geo = float(np.exp(z01.mean()))
            y11_geo = float(np.exp(z11.mean()))
            interaction_ratio = float(np.exp(boot["delta"]))
            interaction_pct = (interaction_ratio - 1.0) * 100.0
            mir_drop_pct = (float(np.exp(z10.mean() - z00.mean())) - 1.0) * 100.0
            llvm_drop_pct = (float(np.exp(z01.mean() - z00.mean())) - 1.0) * 100.0
            joint_drop_pct = (float(np.exp(z11.mean() - z00.mean())) - 1.0) * 100.0

            results.append(
                {
                    "mir_pass": mir_pass,
                    "llvm_pass": llvm_pass,
                    "y00_mean": y00_geo,
                    "y10_mean": y10_geo,
                    "y01_mean": y01_geo,
                    "y11_mean": y11_geo,
                    "delta": boot["delta"],
                    "interaction_ratio": interaction_ratio,
                    "interaction_pct": interaction_pct,
                    "mir_drop_pct": mir_drop_pct,
                    "llvm_drop_pct": llvm_drop_pct,
                    "joint_drop_pct": joint_drop_pct,
                    "ci_low": boot["ci_low"],
                    "ci_high": boot["ci_high"],
                    "p_value": boot["p_value"],
                    "n_y00": int(len(y00)),
                    "n_y10": int(len(y10)),
                    "n_y01": int(len(y01)),
                    "n_y11": int(len(y11)),
                }
            )

    return pd.DataFrame(results)


def plot_forest(results_df, output_dir):
    top_k = results_df[results_df["significant"]].sort_values("abs_delta", ascending=False).head(50).copy()
    if top_k.empty:
        top_k = results_df.sort_values("abs_delta", ascending=False).head(50).copy()
    if top_k.empty:
        return

    top_k["label"] = top_k["mir_pass"] + " + " + top_k["llvm_pass"]
    top_k = top_k.sort_values("delta", ascending=True).reset_index(drop=True)
    fig_h = max(10.0, 0.38 * len(top_k) + 2.0)
    plt.figure(figsize=(12, fig_h))
    point_colors = np.where(top_k["delta"] < 0, "#1f77b4", "#d62728")

    plt.errorbar(
        x=top_k["delta"],
        y=range(len(top_k)),
        xerr=[top_k["delta"] - top_k["ci_low"], top_k["ci_high"] - top_k["delta"]],
        fmt="none",
        ecolor="#444444",
        capsize=4,
        elinewidth=1.2,
        zorder=1,
    )
    plt.scatter(top_k["delta"], range(len(top_k)), c=point_colors, s=24, zorder=2)
    plt.yticks(range(len(top_k)), top_k["label"], fontsize=8)
    plt.axvline(x=0, color="r", linestyle="--", linewidth=1.2)
    plt.xlabel("Interaction Effect (Delta, bootstrap 95% CI)")
    plt.title("Top Interactions from Raw-Run Bootstrap DiD")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "top_interactions_forest.png"), bbox_inches="tight")
    plt.savefig(os.path.join(output_dir, "top_interactions_forest.pdf"), bbox_inches="tight")
    plt.close()


def main():
    print(f"Using results directory: {DATA_DIR}")
    print("Loading raw data...")
    raw_df = load_raw_experiment_data()

    print("Analyzing bootstrap DiD interactions...")
    results_df = analyze_interactions(raw_df)
    if results_df is None or results_df.empty:
        print("No interactions calculated.")
        return

    results_df, summary = classify_effect_strength(results_df)
    results_df = results_df.sort_values(["significant", "abs_delta", "delta"], ascending=[False, False, True]).reset_index(
        drop=True
    )

    results_csv = os.path.join(OUTPUT_DIR, "interaction_results.csv")
    results_df.to_csv(results_csv, index=False)
    print(f"Saved results to {results_csv}")
    print(
        "Effect thresholds: "
        f"strong={summary['strong_threshold']:.6f}, "
        f"extreme={summary['extreme_threshold']:.6f}"
    )
    print(
        "Significant interactions: "
        f"{summary['highlighted_count']} total, "
        f"{summary['negative_highlighted_count']} negative, "
        f"{summary['positive_highlighted_count']} positive"
    )

    pivot_delta = results_df.pivot(index="mir_pass", columns="llvm_pass", values="delta")
    plt.figure(figsize=(12, 10))
    sns.heatmap(pivot_delta, cmap="RdBu_r", center=0, annot=False)
    plt.title("Interaction Effect (Delta) Heatmap (Raw Bootstrap DiD)")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "interaction_heatmap.png"), bbox_inches="tight")
    plt.savefig(os.path.join(OUTPUT_DIR, "interaction_heatmap.pdf"), bbox_inches="tight")
    plt.close()

    plot_forest(results_df, OUTPUT_DIR)

    top_row = results_df.sort_values("abs_delta", ascending=False).iloc[0]
    print("\nTop Interaction Example (by |delta|):")
    print(f"MIR: {top_row['mir_pass']}, LLVM: {top_row['llvm_pass']}")
    print(f"y00 (Base): {top_row['y00_mean']:.4f}")
    print(f"y10 (No MIR): {top_row['y10_mean']:.4f}")
    print(f"y01 (No LLVM): {top_row['y01_mean']:.4f}")
    print(f"y11 (Neither): {top_row['y11_mean']:.4f}")
    print(f"Delta: {top_row['delta']:.4f}")
    print(f"95% CI: [{top_row['ci_low']:.4f}, {top_row['ci_high']:.4f}]")
    print(f"Interaction pct: {top_row['interaction_pct']:.2f}%")
    print(f"Adjusted p: {top_row['p_adj']:.4g}")


if __name__ == "__main__":
    main()
