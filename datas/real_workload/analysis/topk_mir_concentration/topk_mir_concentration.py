import argparse
import csv
import math
import os
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt


def _clean_pass_name(x: object) -> str:
    if x is None:
        return "None"
    s = str(x).strip()
    if s == "" or s.lower() in {"none", "baseline", "nan", "n/a", "na"}:
        return "None"
    return s


def _read_float(r: Dict[str, str], key: str) -> Optional[float]:
    try:
        s = str(r.get(key, "")).strip()
        if s == "" or s.lower() == "nan":
            return None
        return float(s)
    except Exception:
        return None


def _is_usable_status(x: object) -> bool:
    s = str(x if x is not None else "").strip().lower()
    if s == "":
        return True
    return s in {"success", "noparsedresults"}


def _mean(xs: Sequence[float]) -> float:
    if not xs:
        return float("nan")
    return float(sum(xs) / len(xs))


def _workload_csvs(benchmark_dir: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for name in sorted(os.listdir(benchmark_dir)):
        if not name.lower().endswith(".csv"):
            continue
        p = os.path.join(benchmark_dir, name)
        if os.path.isfile(p):
            out.append((os.path.splitext(name)[0], p))
    return out


def _load_groups(*, experiment_csv: str, metric_col: str) -> Dict[Tuple[str, str], List[float]]:
    groups: Dict[Tuple[str, str], List[float]] = {}
    with open(experiment_csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not _is_usable_status(r.get("Status", "")):
                continue
            y = _read_float(r, metric_col)
            if y is None or not (y > 0.0):
                continue
            mir_p = _clean_pass_name(r.get("MIR_Pass"))
            llvm_p = _clean_pass_name(r.get("LLVM_Pass"))
            # Raw workload CSVs may encode the analysis baseline as
            # (LLVM_Pass=None, MIR_Pass=All). Remap only that baseline row.
            if mir_p == "All" and llvm_p == "None":
                mir_p = "None"
            # Any remaining All label is not part of the single-pass DiD grid.
            if mir_p == "All" or llvm_p == "All":
                continue
            groups.setdefault((mir_p, llvm_p), []).append(math.log(y))
    return groups


def _compute_pairwise_deltas(*, groups: Dict[Tuple[str, str], List[float]]) -> List[Dict[str, object]]:
    z00 = groups.get(("None", "None"), [])
    if not z00:
        return []
    base_mean = _mean(z00)

    mir_list = sorted({m for (m, _) in groups.keys() if m not in {"None", "All"}})
    llvm_list = sorted({l for (_, l) in groups.keys() if l not in {"None", "All"}})

    rows: List[Dict[str, object]] = []
    for m in mir_list:
        z10 = groups.get((m, "None"), [])
        mu10 = _mean(z10) if z10 else base_mean
        for l in llvm_list:
            z01 = groups.get(("None", l), [])
            z11 = groups.get((m, l), [])
            if not z01 or not z11:
                continue
            mu01 = _mean(z01)
            mu11 = _mean(z11)
            delta = (mu01 - mu11) - (base_mean - mu10)
            if not (delta == delta):
                continue
            rows.append(
                {
                    "mir_pass": m,
                    "llvm_pass": l,
                    "delta": float(delta),
                    "abs_delta": abs(float(delta)),
                }
            )
    rows.sort(key=lambda r: float(r["abs_delta"]), reverse=True)
    return rows


def _topk_metrics(rows: List[Dict[str, object]], k: int) -> Optional[Dict[str, object]]:
    top = rows[: max(0, int(k))]
    if not top:
        return None

    counts: Dict[str, int] = {}
    mass: Dict[str, float] = {}
    total_mass = 0.0
    for r in top:
        mir = str(r.get("mir_pass", "")).strip()
        v = float(r.get("abs_delta", 0.0))
        counts[mir] = counts.get(mir, 0) + 1
        mass[mir] = mass.get(mir, 0.0) + v
        total_mass += v

    count_items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    mass_items = sorted(mass.items(), key=lambda kv: (-kv[1], kv[0]))
    unique_mirs = len(counts)
    top3_count_percentage = sum(v for _, v in count_items[:3]) / float(len(top))
    top5_absdelta_percentage = sum(v for _, v in mass_items[:5]) / total_mass if total_mass > 0 else 0.0
    top1_mir = count_items[0][0]
    top1_count_percentage = count_items[0][1] / float(len(top))

    return {
        "K": int(k),
        "unique_mir_in_topk": int(unique_mirs),
        "top3_count_percentage": float(top3_count_percentage),
        "top5_absdelta_percentage": float(top5_absdelta_percentage),
        "top1_mir": top1_mir,
        "top1_count_percentage": float(top1_count_percentage),
    }


def build_summary_rows(*, benchmark_dir: str, metric_col: str, ks: Sequence[int]) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for workload, csv_path in _workload_csvs(benchmark_dir):
        groups = _load_groups(experiment_csv=csv_path, metric_col=metric_col)
        rows = _compute_pairwise_deltas(groups=groups)
        if not rows:
            print(f"Skipping {workload}: no complete pairwise interaction rows for {metric_col}.")
            continue
        print(f"Processed {workload}: {len(rows)} interaction pairs.")
        for k in ks:
            metrics = _topk_metrics(rows, int(k))
            if metrics is None:
                continue
            out.append(
                {
                    "workload": workload,
                    "K": int(metrics["K"]),
                    "unique_mir_in_topk": int(metrics["unique_mir_in_topk"]),
                    "top3_count_percentage": float(metrics["top3_count_percentage"]),
                    "top5_absdelta_percentage": float(metrics["top5_absdelta_percentage"]),
                    "top1_mir": str(metrics["top1_mir"]),
                    "top1_count_percentage": float(metrics["top1_count_percentage"]),
                }
            )
    return out


def write_summary_csv(*, rows: List[Dict[str, object]], out_csv: str) -> None:
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "workload",
                "K",
                "unique_mir_in_topk",
                "top3_count_percentage",
                "top5_absdelta_percentage",
                "top1_mir",
                "top1_count_percentage",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    r["workload"],
                    r["K"],
                    r["unique_mir_in_topk"],
                    f"{float(r['top3_count_percentage']):.6f}",
                    f"{float(r['top5_absdelta_percentage']):.6f}",
                    r["top1_mir"],
                    f"{float(r['top1_count_percentage']):.6f}",
                ]
            )


def plot_summary(
    *,
    rows: List[Dict[str, object]],
    ks: Sequence[int],
    out_png: str,
    out_pdf: str,
    title: str,
    font_scale: float,
) -> None:
    if not rows:
        return

    workloads = sorted({str(r["workload"]) for r in rows})
    k_values = [int(k) for k in ks]
    row_map = {(str(r["workload"]), int(r["K"])): r for r in rows}

    s = float(font_scale)
    fig, axes = plt.subplots(3, 1, figsize=(12.0, 11.0), sharex=True)
    metrics = [
        ("unique_mir_in_topk", "Unique MIR Passes in Top-K", False),
        ("top3_count_percentage", "Top-3 MIR Percentage of Top-K Pair Count", True),
        ("top5_absdelta_percentage", "Top-5 MIR Percentage of Top-K |Delta| Mass", True),
    ]
    colors = ["#4c78a8", "#f58518", "#54a24b", "#e45756"]
    width = 0.36 if len(k_values) <= 2 else 0.22
    x = list(range(len(workloads)))
    center = (len(k_values) - 1) / 2.0

    for ax, (metric_key, ylabel, is_share) in zip(axes, metrics):
        for idx, k in enumerate(k_values):
            vals: List[float] = []
            for wl in workloads:
                row = row_map.get((wl, k))
                vals.append(float(row[metric_key]) if row is not None else 0.0)
            xpos = [xi + (idx - center) * width for xi in x]
            ax.bar(xpos, vals, width=width, color=colors[idx % len(colors)], label=f"Top-{k}")

        ax.set_ylabel(ylabel, fontsize=11.5 * s)
        ax.grid(axis="y", linestyle="--", alpha=0.35)
        ax.tick_params(axis="y", labelsize=10.5 * s)
        if is_share:
            ax.set_ylim(0.0, 1.05)

    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(workloads, fontsize=11.0 * s)
    axes[-1].set_xlabel("Workload", fontsize=12.0 * s)
    axes[0].legend(ncol=max(1, len(k_values)), fontsize=10.0 * s, frameon=False, loc="upper right")
    fig.suptitle(title, fontsize=15.0 * s, fontweight="bold")
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.965])

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=450, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark-dir", default=r"d:\MIR_LLVM_NEW\datas\real_workload")
    ap.add_argument("--out-dir", default=r"d:\MIR_LLVM_NEW\datas\real_workload\analysis\topk_mir_concentration")
    ap.add_argument("--metric-col", default="TotalRuntime(s)")
    ap.add_argument("--ks", default="50,100")
    ap.add_argument("--title", default="Top-K MIR concentration of strongest cross-layer interactions")
    ap.add_argument("--font-scale", type=float, default=1.0)
    args = ap.parse_args()

    benchmark_dir = os.path.abspath(str(args.benchmark_dir))
    out_dir = os.path.abspath(str(args.out_dir))
    metric_col = str(args.metric_col)
    ks = [int(s.strip()) for s in str(args.ks).split(",") if str(s).strip()]
    ks = [k for k in ks if k > 0]
    if not ks:
        raise ValueError("At least one positive K must be provided.")

    rows = build_summary_rows(benchmark_dir=benchmark_dir, metric_col=metric_col, ks=ks)

    tag = f"{metric_col.replace('/', '_')}_top{'-'.join(str(k) for k in ks)}"
    out_csv = os.path.join(out_dir, f"topk_mir_concentration_summary_{tag}.csv")
    out_png = os.path.join(out_dir, f"topk_mir_concentration_{tag}.png")
    out_pdf = os.path.join(out_dir, f"topk_mir_concentration_{tag}.pdf")

    write_summary_csv(rows=rows, out_csv=out_csv)
    plot_summary(
        rows=rows,
        ks=ks,
        out_png=out_png,
        out_pdf=out_pdf,
        title=str(args.title),
        font_scale=float(args.font_scale),
    )
    print(f"Saved summary CSV to {out_csv}")
    print(f"Saved plot to {out_png}")
    print(f"Saved plot to {out_pdf}")


if __name__ == "__main__":
    main()
