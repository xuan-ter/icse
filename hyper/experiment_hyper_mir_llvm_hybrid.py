import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from statistics import mean, median


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = SCRIPT_DIR
DEFAULT_JSON_PATH = os.path.join(WORKSPACE_ROOT, "table", "table_json", "combined_experiment_matrix.json")
DEFAULT_RESULTS_ROOT = os.path.join(PROJECT_ROOT, "results")
BENCH_VARIANT = "hyper"
DEFAULT_WARMUP_RUNS = 1


def get_combinations(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("combinations", [])


def find_combo_start_index(combos, start_exp_id):
    if not start_exp_id:
        return None
    for idx, combo in enumerate(combos):
        name = combo.get("name") or combo.get("Experiment_ID")
        if name == start_exp_id:
            return idx
    return None


def labels_from_combo(combo):
    mir_pass_label = "N/A"
    llvm_pass_label = "None"
    if combo.get("mir"):
        if isinstance(combo["mir"], dict):
            mir_pass_label = combo["mir"].get("pass", "N/A")
        else:
            mir_pass_label = str(combo["mir"])
    if combo.get("llvm"):
        if isinstance(combo["llvm"], dict):
            llvm_pass_label = combo["llvm"].get("pass", "None")
        else:
            llvm_pass_label = str(combo["llvm"])
    return llvm_pass_label, mir_pass_label


def clean_project(env=None):
    target_dir = os.path.join(PROJECT_ROOT, "target")
    if os.path.exists(target_dir):
        try:
            shutil.rmtree(target_dir)
            return
        except Exception:
            if env is None:
                env = os.environ.copy()
            subprocess.run(
                ["cargo", "+nightly", "clean"],
                cwd=PROJECT_ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def compose_rustflags_from_combo(combo):
    parts = ["-C opt-level=3"]
    if combo.get("mir") and isinstance(combo["mir"], dict) and combo["mir"].get("switches"):
        switches = ",".join(combo["mir"]["switches"])
        parts.append(f"-Z mir-enable-passes={switches}")
    if combo.get("llvm") and isinstance(combo["llvm"], dict) and combo["llvm"].get("switches"):
        for switch in combo["llvm"]["switches"]:
            parts.append(f"-C llvm-args={switch}")
    if "RUSTFLAGS" in combo and combo["RUSTFLAGS"]:
        parts.append(combo["RUSTFLAGS"])
    return " ".join(parts)


def build_bench(env, bench_name, logf, retries=2):
    backoff = 0.5
    last_err = ""
    cmd = [
        "cargo",
        "+nightly",
        "bench",
        "--bench",
        bench_name,
        "--features",
        "full",
        "--no-run",
        "--quiet",
    ]
    for _ in range(retries + 1):
        r = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if r.returncode == 0:
            return True, "Success"
        err = r.stderr or ""
        last_err = err
        if err.strip():
            logf.write(err + "\n")
            logf.flush()
        if ("Text file busy (os error 26)" in err) or ("never executed" in err):
            time.sleep(backoff)
            backoff = min(backoff * 2, 4.0)
            continue
        return False, "BuildFailed"
    if ("Text file busy (os error 26)" in last_err) or ("never executed" in last_err) or ("failed to run custom build command" in last_err):
        return False, "Skipped"
    return False, "BuildFailed"


def find_bench_exe(bench_name):
    deps_dir = os.path.join(PROJECT_ROOT, "target", "release", "deps")
    if not os.path.isdir(deps_dir):
        return None
    prefix = f"{bench_name}-"
    candidates = []
    for name in os.listdir(deps_dir):
        if not name.startswith(prefix):
            continue
        if name.endswith(".d"):
            continue
        path = os.path.join(deps_dir, name)
        if not os.path.isfile(path):
            continue
        if not os.access(path, os.X_OK):
            continue
        try:
            mtime = os.path.getmtime(path)
        except Exception:
            mtime = 0
        candidates.append((mtime, path))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def resolve_bench_filter(exe_path, requested_filter):
    p = subprocess.run([exe_path, "--list"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        return requested_filter

    names = []
    for line in (p.stdout or "").splitlines():
        if ":" not in line:
            continue
        name, kind = line.split(":", 1)
        kind = kind.strip()
        if kind.startswith("bench") or kind.startswith("benchmark"):
            names.append(name.strip())

    if not names:
        return requested_filter
    if requested_filter in names:
        return requested_filter
    return names[0]


def run_benchmark(exe_path, bench_filter, repeat):
    total_wall = 0.0
    last_err = ""
    last_out = ""
    ns_per_iter = ""
    mbps = ""
    for _ in range(repeat):
        t0 = time.perf_counter()
        p = subprocess.run(
            [exe_path, "--bench", bench_filter, "--exact", "--test-threads", "1", "-q"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        t1 = time.perf_counter()
        if p.returncode != 0:
            last_err = (p.stdout or "").strip()
            return None, "", "", last_err
        last_out = p.stdout or ""
        total_wall += (t1 - t0)

        m_ns = re.search(r"bench:\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*ns/iter", last_out)
        if m_ns:
            ns_per_iter = m_ns.group(1).replace(",", "")
        m_mbps = re.search(r"=\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*MB/s", last_out)
        if m_mbps:
            mbps = m_mbps.group(1).replace(",", "")

    if not ns_per_iter:
        last_err = last_out.strip()
        return None, "", "", last_err

    return total_wall, ns_per_iter, mbps, last_err


def aggregate_summary(rows):
    by = defaultdict(list)
    for row in rows:
        if row.get("Status") != "Success":
            continue
        key = (row.get("Variant", BENCH_VARIANT), row["ConfigName"])
        by[key].append(row)

    out = []
    for (variant, cfg), rs in sorted(by.items()):
        def values(key, cast=float):
            xs = []
            for row in rs:
                try:
                    xs.append(cast(row[key]))
                except Exception:
                    pass
            return sorted(xs)

        def avg_value(key, cast=float):
            xs = values(key, cast)
            return mean(xs) if xs else None

        def med_value(key, cast=float):
            xs = values(key, cast)
            return median(xs) if xs else None

        def percentile(xs, p):
            if not xs:
                return None
            if len(xs) == 1:
                return float(xs[0])
            pos = (len(xs) - 1) * p
            lo = int(pos)
            hi = min(lo + 1, len(xs) - 1)
            frac = pos - lo
            return float(xs[lo]) * (1.0 - frac) + float(xs[hi]) * frac

        def iqr_value(key, cast=float):
            xs = values(key, cast)
            if not xs:
                return None
            q1 = percentile(xs, 0.25)
            q3 = percentile(xs, 0.75)
            if q1 is None or q3 is None:
                return None
            return q3 - q1

        out.append(
            {
                "Variant": variant,
                "ConfigName": cfg,
                "n": str(len(rs)),
                "wall_mean": f"{avg_value('TotalRuntime(s)'):.6f}" if avg_value("TotalRuntime(s)") is not None else "",
                "wall_med": f"{med_value('TotalRuntime(s)'):.6f}" if med_value("TotalRuntime(s)") is not None else "",
                "wall_iqr": f"{iqr_value('TotalRuntime(s)'):.6f}" if iqr_value("TotalRuntime(s)") is not None else "",
                "ns_mean": f"{avg_value('NsPerIter'):.6f}" if avg_value("NsPerIter") is not None else "",
                "ns_med": f"{med_value('NsPerIter'):.6f}" if med_value("NsPerIter") is not None else "",
                "ns_iqr": f"{iqr_value('NsPerIter'):.6f}" if iqr_value("NsPerIter") is not None else "",
                "mbps_mean": f"{avg_value('MBps'):.6f}" if avg_value("MBps") is not None else "",
                "mbps_med": f"{med_value('MBps'):.6f}" if med_value("MBps") is not None else "",
                "mbps_iqr": f"{iqr_value('MBps'):.6f}" if iqr_value("MBps") is not None else "",
                "compile_mean": f"{avg_value('CompileTime(s)'):.6f}" if avg_value("CompileTime(s)") is not None else "",
                "compile_med": f"{med_value('CompileTime(s)'):.6f}" if med_value("CompileTime(s)") is not None else "",
                "compile_iqr": f"{iqr_value('CompileTime(s)'):.6f}" if iqr_value("CompileTime(s)") is not None else "",
                "size_mean": f"{avg_value('BinarySize(Bytes)', int):.6f}" if avg_value("BinarySize(Bytes)", int) is not None else "",
                "size_med": f"{med_value('BinarySize(Bytes)', int):.0f}" if med_value("BinarySize(Bytes)", int) is not None else "",
            }
        )
    return out


def compute_interaction(summary_rows, metric_key, smaller_is_better=True):
    idx = {(row["Variant"], row["ConfigName"]): row for row in summary_rows}
    out = []
    for variant in sorted({row["Variant"] for row in summary_rows}):
        def get(cfg):
            row = idx.get((variant, cfg))
            if not row:
                return None
            value = row.get(metric_key, "")
            if value == "":
                return None
            try:
                return float(value)
            except Exception:
                return None

        a = get("M_on_L_on")
        b = get("M_on_L_off")
        c = get("M_off_L_on")
        d = get("M_off_L_off")
        if None in (a, b, c, d):
            continue

        effect = (lambda x: -x) if smaller_is_better else (lambda x: x)
        delta = effect(a) - effect(b) - effect(c) + effect(d)
        out.append(
            {
                "Variant": variant,
                "metric": metric_key,
                "delta": f"{delta:.6f}",
                "M_on_L_on": f"{a:.6f}",
                "M_on_L_off": f"{b:.6f}",
                "M_off_L_on": f"{c:.6f}",
                "M_off_L_off": f"{d:.6f}",
            }
        )
    return out


def build_volatility_summary(summary_rows):
    def as_float(value):
        if value in ("", None):
            return None
        try:
            return float(value)
        except Exception:
            return None

    out = []
    for row in summary_rows:
        ns_med = as_float(row.get("ns_med"))
        ns_iqr = as_float(row.get("ns_iqr"))
        compile_med = as_float(row.get("compile_med"))
        compile_iqr = as_float(row.get("compile_iqr"))

        ns_iqr_ratio = None
        if ns_med not in (None, 0.0) and ns_iqr is not None:
            ns_iqr_ratio = ns_iqr / ns_med

        compile_iqr_ratio = None
        if compile_med not in (None, 0.0) and compile_iqr is not None:
            compile_iqr_ratio = compile_iqr / compile_med

        out.append(
            {
                "Variant": row["Variant"],
                "ConfigName": row["ConfigName"],
                "n": row["n"],
                "wall_mean": row["wall_mean"],
                "wall_med": row["wall_med"],
                "wall_iqr": row["wall_iqr"],
                "ns_mean": row["ns_mean"],
                "ns_med": row["ns_med"],
                "ns_iqr": row["ns_iqr"],
                "ns_iqr_ratio": f"{ns_iqr_ratio:.6f}" if ns_iqr_ratio is not None else "",
                "mbps_mean": row["mbps_mean"],
                "mbps_med": row["mbps_med"],
                "mbps_iqr": row["mbps_iqr"],
                "compile_mean": row["compile_mean"],
                "compile_med": row["compile_med"],
                "compile_iqr": row["compile_iqr"],
                "compile_iqr_ratio": f"{compile_iqr_ratio:.6f}" if compile_iqr_ratio is not None else "",
                "size_mean": row["size_mean"],
                "size_med": row["size_med"],
            }
        )

    def sort_key(row):
        ns_ratio = as_float(row["ns_iqr_ratio"])
        ns_iqr = as_float(row["ns_iqr"])
        compile_ratio = as_float(row["compile_iqr_ratio"])
        compile_iqr = as_float(row["compile_iqr"])
        return (
            ns_ratio if ns_ratio is not None else -1.0,
            ns_iqr if ns_iqr is not None else -1.0,
            compile_ratio if compile_ratio is not None else -1.0,
            compile_iqr if compile_iqr is not None else -1.0,
            row["Variant"],
            row["ConfigName"],
        )

    out.sort(key=sort_key, reverse=True)
    return out


def measure_combination(combo, runs, bench_name, bench_filter, bench_repeat, logf):
    name = combo.get("name") or combo.get("Experiment_ID") or "Unknown"
    llvm_pass, mir_pass = labels_from_combo(combo)

    env = os.environ.copy()
    env.setdefault("RUSTUP_TOOLCHAIN", "nightly")
    cargo_bin = os.path.expanduser("~/.cargo/bin")
    if cargo_bin and cargo_bin not in env.get("PATH", ""):
        env["PATH"] = f"{cargo_bin}:{env.get('PATH', '')}"

    rustflags = compose_rustflags_from_combo(combo)
    env["RUSTFLAGS"] = rustflags

    results = []
    msg1 = f"[Exp] {name}"
    msg2 = f"[Flags] {rustflags}"
    msg3 = f"[Bench] {bench_name}::{bench_filter} x{bench_repeat}"
    print(msg1)
    print(msg2)
    print(msg3)
    logf.write(msg1 + "\n")
    logf.write(msg2 + "\n")
    logf.write(msg3 + "\n")
    logf.flush()

    clean_project(env)

    t0 = time.perf_counter()
    ok, status = build_bench(env, bench_name, logf)
    t1 = time.perf_counter()
    compile_time = t1 - t0

    if not ok:
        results.append(
            {
                "ConfigName": name,
                "Variant": BENCH_VARIANT,
                "RunID": 1,
                "LLVM_Pass": llvm_pass,
                "MIR_Pass": mir_pass,
                "BinarySize(Bytes)": 0,
                "NsPerIter": "",
                "MBps": "",
                "TotalRuntime(s)": 0,
                "CompileTime(s)": f"{compile_time:.6f}",
                "BenchName": bench_name,
                "BenchFilter": bench_filter,
                "BenchRepeat": bench_repeat,
                "Status": status,
            }
        )
        return results

    exe_path = find_bench_exe(bench_name)
    if not exe_path:
        results.append(
            {
                "ConfigName": name,
                "Variant": BENCH_VARIANT,
                "RunID": 1,
                "LLVM_Pass": llvm_pass,
                "MIR_Pass": mir_pass,
                "BinarySize(Bytes)": 0,
                "NsPerIter": "",
                "MBps": "",
                "TotalRuntime(s)": 0,
                "CompileTime(s)": f"{compile_time:.6f}",
                "BenchName": bench_name,
                "BenchFilter": bench_filter,
                "BenchRepeat": bench_repeat,
                "Status": "NoBinary",
            }
        )
        return results

    try:
        size = os.path.getsize(exe_path)
    except Exception:
        size = 0

    resolved_bench_filter = resolve_bench_filter(exe_path, bench_filter)
    if resolved_bench_filter != bench_filter:
        msg = f"[BenchFilterResolved] {bench_filter} -> {resolved_bench_filter}"
        print(msg)
        logf.write(msg + "\n")
        logf.flush()

    print(f"[Exp] {name} Warmup {DEFAULT_WARMUP_RUNS}/{DEFAULT_WARMUP_RUNS}")
    logf.write(f"[Exp] {name} Warmup {DEFAULT_WARMUP_RUNS}/{DEFAULT_WARMUP_RUNS}\n")
    logf.flush()
    wall_time, ns_per_iter, mbps, run_err = run_benchmark(exe_path, resolved_bench_filter, bench_repeat)
    if wall_time is None:
        if run_err:
            logf.write("[RunError] " + run_err + "\n")
            logf.flush()
        logf.write("[SkipConfig] Warmup run failed\n")
        logf.flush()
        return results

    print(f"[WarmupResult] Size={size}B, Compile={compile_time:.6f}s, Wall={wall_time:.6f}s, NsPerIter={ns_per_iter}, MBps={mbps}")

    for run_id in range(1, runs + 1):
        run_msg = f"[Exp] {name} Iteration {run_id}/{runs}"
        print(run_msg)
        logf.write(run_msg + "\n")
        logf.flush()

        wall_time, ns_per_iter, mbps, run_err = run_benchmark(exe_path, resolved_bench_filter, bench_repeat)
        if wall_time is None:
            if run_err:
                logf.write("[RunError] " + run_err + "\n")
                logf.flush()
            results.append(
                {
                    "ConfigName": name,
                    "Variant": BENCH_VARIANT,
                    "RunID": run_id,
                    "LLVM_Pass": llvm_pass,
                    "MIR_Pass": mir_pass,
                    "BinarySize(Bytes)": size,
                    "NsPerIter": "",
                    "MBps": "",
                    "TotalRuntime(s)": 0,
                    "CompileTime(s)": f"{compile_time:.6f}",
                    "BenchName": bench_name,
                    "BenchFilter": resolved_bench_filter,
                    "BenchRepeat": bench_repeat,
                    "Status": "RunFailed",
                }
            )
            break

        print(f"[Result] Size={size}B, Compile={compile_time:.6f}s, Wall={wall_time:.6f}s, NsPerIter={ns_per_iter}, MBps={mbps}")
        results.append(
            {
                "ConfigName": name,
                "Variant": BENCH_VARIANT,
                "RunID": run_id,
                "LLVM_Pass": llvm_pass,
                "MIR_Pass": mir_pass,
                "BinarySize(Bytes)": size,
                "NsPerIter": ns_per_iter,
                "MBps": mbps,
                "TotalRuntime(s)": f"{wall_time:.6f}",
                "CompileTime(s)": f"{compile_time:.6f}",
                "BenchName": bench_name,
                "BenchFilter": resolved_bench_filter,
                "BenchRepeat": bench_repeat,
                "Status": "Success",
            }
        )

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", nargs="?", default=DEFAULT_JSON_PATH)
    parser.add_argument("--json-path", default="")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--start-exp", default="")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--bench-name", default="end_to_end")
    parser.add_argument("--bench-filter", default="http1_consecutive_x1_both_100mb")
    parser.add_argument("--bench-repeat", type=int, default=1)
    args = parser.parse_args()

    config_path = args.json_path.strip() or str(args.config_file)
    if not os.path.exists(config_path):
        raise SystemExit(f"JSON path not found: {config_path}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_out = args.out_dir.strip() or args.output_dir.strip() or os.path.join(DEFAULT_RESULTS_ROOT, ts)
    os.makedirs(base_out, exist_ok=True)

    results_csv = os.path.join(base_out, "experiment_results.csv")
    summary_csv = os.path.join(base_out, "summary_medians.csv")
    inter_csv = os.path.join(base_out, "interaction_delta.csv")
    volatility_csv = os.path.join(base_out, "volatility_summary.csv")
    exec_log = os.path.join(base_out, "experiment_execution.log")

    combos = get_combinations(config_path)
    start_index = 0
    if args.start_exp.strip():
        found = find_combo_start_index(combos, args.start_exp.strip())
        if found is None:
            raise SystemExit(f'--start-exp "{args.start_exp.strip()}" not found in combinations')
        start_index = found
    elif args.start > 0:
        start_index = args.start

    if start_index > 0:
        combos = combos[start_index:]
    if args.limit and args.limit > 0:
        combos = combos[: args.limit]

    with open(exec_log, "w", encoding="utf-8") as logf:
        print(f"Total Rows: {len(combos)}")
        logf.write(f"Total Rows: {len(combos)}\n")
        logf.flush()

        with open(results_csv, "w", encoding="utf-8", newline="") as outcsv:
            writer = csv.DictWriter(
                outcsv,
                fieldnames=[
                    "ConfigName",
                    "Variant",
                    "RunID",
                    "LLVM_Pass",
                    "MIR_Pass",
                    "BinarySize(Bytes)",
                    "NsPerIter",
                    "MBps",
                    "TotalRuntime(s)",
                    "CompileTime(s)",
                    "BenchName",
                    "BenchFilter",
                    "BenchRepeat",
                    "Status",
                ],
            )
            writer.writeheader()
            outcsv.flush()

            for combo in combos:
                rows = measure_combination(
                    combo,
                    args.runs,
                    args.bench_name,
                    args.bench_filter,
                    args.bench_repeat,
                    logf,
                )
                for row in rows:
                    writer.writerow(row)
                outcsv.flush()

    rows = []
    with open(results_csv, "r", encoding="utf-8") as incsv:
        reader = csv.DictReader(incsv)
        for row in reader:
            rows.append(row)

    summary = aggregate_summary(rows)
    with open(summary_csv, "w", encoding="utf-8", newline="") as outcsv:
        writer = csv.DictWriter(
            outcsv,
            fieldnames=[
                "Variant",
                "ConfigName",
                "n",
                "wall_mean",
                "wall_med",
                "wall_iqr",
                "ns_mean",
                "ns_med",
                "ns_iqr",
                "mbps_mean",
                "mbps_med",
                "mbps_iqr",
                "compile_mean",
                "compile_med",
                "compile_iqr",
                "size_mean",
                "size_med",
            ],
        )
        writer.writeheader()
        for row in summary:
            writer.writerow(row)

    volatility = build_volatility_summary(summary)
    with open(volatility_csv, "w", encoding="utf-8", newline="") as outcsv:
        writer = csv.DictWriter(
            outcsv,
            fieldnames=[
                "Variant",
                "ConfigName",
                "n",
                "wall_mean",
                "wall_med",
                "wall_iqr",
                "ns_mean",
                "ns_med",
                "ns_iqr",
                "ns_iqr_ratio",
                "mbps_mean",
                "mbps_med",
                "mbps_iqr",
                "compile_mean",
                "compile_med",
                "compile_iqr",
                "compile_iqr_ratio",
                "size_mean",
                "size_med",
            ],
        )
        writer.writeheader()
        for row in volatility:
            writer.writerow(row)

    inter = compute_interaction(summary, "ns_med", smaller_is_better=True)
    if inter:
        with open(inter_csv, "w", encoding="utf-8", newline="") as outcsv:
            writer = csv.DictWriter(
                outcsv,
                fieldnames=["Variant", "metric", "delta", "M_on_L_on", "M_on_L_off", "M_off_L_on", "M_off_L_off"],
            )
            writer.writeheader()
            for row in inter:
                writer.writerow(row)

    print(base_out)


if __name__ == "__main__":
    main()
