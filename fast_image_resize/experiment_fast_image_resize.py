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
BENCH_VARIANT = "fast_image_resize"


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


def build_run_command(exe_path, sample_size, measurement_time, warm_up_time, noplot):
    cmd = [exe_path, "--color", "never"]
    if noplot:
        cmd.append("--noplot")
    if sample_size and sample_size > 0:
        cmd.extend(["--sample-size", str(sample_size)])
    if measurement_time and measurement_time > 0:
        cmd.extend(["--measurement-time", f"{measurement_time}"])
    if warm_up_time and warm_up_time > 0:
        cmd.extend(["--warm-up-time", f"{warm_up_time}"])
    return cmd


def run_benchmark(exe_path, env, sample_size, measurement_time, warm_up_time, noplot):
    cmd = build_run_command(exe_path, sample_size, measurement_time, warm_up_time, noplot)
    t0 = time.perf_counter()
    p = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    t1 = time.perf_counter()
    return p.returncode, t1 - t0, p.stdout or ""


def case_matches(case_filter_re, bench_group, function_name, parameter):
    if not case_filter_re:
        return True
    label = "::".join(part for part in [bench_group, function_name, parameter] if part)
    return bool(case_filter_re.search(label))


def extract_benchmark_labels(output):
    labels = []
    seen = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        match = re.match(r"Benchmarking\s+(.+?)(?::|$)", line)
        if not match:
            continue
        label = match.group(1).strip()
        if "/" not in label:
            continue
        if label in seen:
            continue
        labels.append(label)
        seen.add(label)
    return labels


def parse_benchmark_label(label):
    parts = [part.strip() for part in label.split("/") if part.strip()]
    if len(parts) < 3:
        return None
    return {
        "BenchGroup": "/".join(parts[:-2]),
        "FunctionName": parts[-2],
        "Parameter": parts[-1],
    }


def extract_last_markdown_table(output):
    blocks = []
    current = []
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if line.startswith("|"):
            current.append(line)
            continue
        if current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)

    for block in reversed(blocks):
        if len(block) >= 3:
            return block
    return []


def parse_markdown_cells(line):
    stripped = line.strip()
    if not stripped.startswith("|"):
        return []
    parts = stripped.split("|")[1:-1]
    return [part.strip() for part in parts]


def detect_arch():
    try:
        return os.uname().machine
    except Exception:
        return ""


def collect_estimates_from_output(output, bench_name, case_filter):
    case_filter_re = re.compile(case_filter) if case_filter else None
    label_map = {}
    bench_groups = set()
    for label in extract_benchmark_labels(output):
        parsed = parse_benchmark_label(label)
        if not parsed:
            continue
        bench_groups.add(parsed["BenchGroup"])
        label_map[(parsed["FunctionName"], parsed["Parameter"])] = parsed["BenchGroup"]

    default_group = next(iter(bench_groups)) if len(bench_groups) == 1 else bench_name
    arch = detect_arch()
    table = extract_last_markdown_table(output)
    if not table:
        return []

    header = parse_markdown_cells(table[0])
    if len(header) < 2:
        return []
    parameters = header[1:]

    rows = []
    for line in table[2:]:
        cells = parse_markdown_cells(line)
        if len(cells) != len(header):
            continue
        function_name = cells[0]
        for parameter, value in zip(parameters, cells[1:]):
            if value in ("", "-"):
                continue
            try:
                estimate_ms = float(value)
            except Exception:
                continue
            bench_group = label_map.get((function_name, parameter), default_group)
            if not case_matches(case_filter_re, bench_group, function_name, parameter):
                continue
            rows.append(
                {
                    "Arch": arch,
                    "BenchGroup": bench_group,
                    "FunctionName": function_name,
                    "Parameter": parameter,
                    "EstimateNs": f"{estimate_ms * 1_000_000.0:.6f}",
                    "EstimateMs": f"{estimate_ms:.6f}",
                }
            )
    return rows


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


def aggregate_summary(rows):
    by = defaultdict(list)
    for row in rows:
        if row.get("Status") != "Success":
            continue
        key = (
            row.get("Variant", BENCH_VARIANT),
            row["ConfigName"],
            row["BenchName"],
            row["BenchGroup"],
            row["FunctionName"],
            row["Parameter"],
        )
        by[key].append(row)

    out = []
    for (variant, cfg, bench_name, bench_group, function_name, parameter), rs in sorted(by.items()):
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
                "BenchName": bench_name,
                "BenchGroup": bench_group,
                "FunctionName": function_name,
                "Parameter": parameter,
                "n": str(len(rs)),
                "estimate_ns_mean": f"{avg_value('EstimateNs'):.6f}" if avg_value("EstimateNs") is not None else "",
                "estimate_ns_med": f"{med_value('EstimateNs'):.6f}" if med_value("EstimateNs") is not None else "",
                "estimate_ns_iqr": f"{iqr_value('EstimateNs'):.6f}" if iqr_value("EstimateNs") is not None else "",
                "estimate_ms_mean": f"{avg_value('EstimateMs'):.6f}" if avg_value("EstimateMs") is not None else "",
                "estimate_ms_med": f"{med_value('EstimateMs'):.6f}" if med_value("EstimateMs") is not None else "",
                "estimate_ms_iqr": f"{iqr_value('EstimateMs'):.6f}" if iqr_value("EstimateMs") is not None else "",
                "wall_mean": f"{avg_value('TotalRuntime(s)'):.6f}" if avg_value("TotalRuntime(s)") is not None else "",
                "wall_med": f"{med_value('TotalRuntime(s)'):.6f}" if med_value("TotalRuntime(s)") is not None else "",
                "wall_iqr": f"{iqr_value('TotalRuntime(s)'):.6f}" if iqr_value("TotalRuntime(s)") is not None else "",
                "compile_mean": f"{avg_value('CompileTime(s)'):.6f}" if avg_value("CompileTime(s)") is not None else "",
                "compile_med": f"{med_value('CompileTime(s)'):.6f}" if med_value("CompileTime(s)") is not None else "",
                "compile_iqr": f"{iqr_value('CompileTime(s)'):.6f}" if iqr_value("CompileTime(s)") is not None else "",
                "size_mean": f"{avg_value('BinarySize(Bytes)', int):.6f}" if avg_value("BinarySize(Bytes)", int) is not None else "",
                "size_med": f"{med_value('BinarySize(Bytes)', int):.0f}" if med_value("BinarySize(Bytes)", int) is not None else "",
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
        estimate_ns_med = as_float(row.get("estimate_ns_med"))
        estimate_ns_iqr = as_float(row.get("estimate_ns_iqr"))
        compile_med = as_float(row.get("compile_med"))
        compile_iqr = as_float(row.get("compile_iqr"))

        estimate_ns_iqr_ratio = None
        if estimate_ns_med not in (None, 0.0) and estimate_ns_iqr is not None:
            estimate_ns_iqr_ratio = estimate_ns_iqr / estimate_ns_med

        compile_iqr_ratio = None
        if compile_med not in (None, 0.0) and compile_iqr is not None:
            compile_iqr_ratio = compile_iqr / compile_med

        out.append(
            {
                "Variant": row["Variant"],
                "ConfigName": row["ConfigName"],
                "BenchName": row["BenchName"],
                "BenchGroup": row["BenchGroup"],
                "FunctionName": row["FunctionName"],
                "Parameter": row["Parameter"],
                "n": row["n"],
                "estimate_ns_mean": row["estimate_ns_mean"],
                "estimate_ns_med": row["estimate_ns_med"],
                "estimate_ns_iqr": row["estimate_ns_iqr"],
                "estimate_ns_iqr_ratio": f"{estimate_ns_iqr_ratio:.6f}" if estimate_ns_iqr_ratio is not None else "",
                "estimate_ms_mean": row["estimate_ms_mean"],
                "estimate_ms_med": row["estimate_ms_med"],
                "estimate_ms_iqr": row["estimate_ms_iqr"],
                "wall_mean": row["wall_mean"],
                "wall_med": row["wall_med"],
                "wall_iqr": row["wall_iqr"],
                "compile_mean": row["compile_mean"],
                "compile_med": row["compile_med"],
                "compile_iqr": row["compile_iqr"],
                "compile_iqr_ratio": f"{compile_iqr_ratio:.6f}" if compile_iqr_ratio is not None else "",
                "size_mean": row["size_mean"],
                "size_med": row["size_med"],
            }
        )

    def sort_key(row):
        estimate_ratio = as_float(row["estimate_ns_iqr_ratio"])
        estimate_iqr = as_float(row["estimate_ns_iqr"])
        compile_ratio = as_float(row["compile_iqr_ratio"])
        compile_iqr = as_float(row["compile_iqr"])
        return (
            estimate_ratio if estimate_ratio is not None else -1.0,
            estimate_iqr if estimate_iqr is not None else -1.0,
            compile_ratio if compile_ratio is not None else -1.0,
            compile_iqr if compile_iqr is not None else -1.0,
            row["Variant"],
            row["ConfigName"],
            row["BenchGroup"],
            row["FunctionName"],
            row["Parameter"],
        )

    out.sort(key=sort_key, reverse=True)
    return out


def compute_interaction(summary_rows, metric_key, smaller_is_better=True):
    idx = {
        (
            row["Variant"],
            row["ConfigName"],
            row["BenchName"],
            row["BenchGroup"],
            row["FunctionName"],
            row["Parameter"],
        ): row
        for row in summary_rows
    }
    series_keys = sorted(
        {
            (
                row["Variant"],
                row["BenchName"],
                row["BenchGroup"],
                row["FunctionName"],
                row["Parameter"],
            )
            for row in summary_rows
        }
    )
    out = []
    for variant, bench_name, bench_group, function_name, parameter in series_keys:
        def get(cfg):
            row = idx.get((variant, cfg, bench_name, bench_group, function_name, parameter))
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
                "BenchName": bench_name,
                "BenchGroup": bench_group,
                "FunctionName": function_name,
                "Parameter": parameter,
                "metric": metric_key,
                "delta": f"{delta:.6f}",
                "M_on_L_on": f"{a:.6f}",
                "M_on_L_off": f"{b:.6f}",
                "M_off_L_on": f"{c:.6f}",
                "M_off_L_off": f"{d:.6f}",
            }
        )
    return out


def make_failure_row(name, llvm_pass, mir_pass, bench_name, compile_time, status, message):
    return {
        "ConfigName": name,
        "Variant": BENCH_VARIANT,
        "RunID": 1,
        "LLVM_Pass": llvm_pass,
        "MIR_Pass": mir_pass,
        "BinarySize(Bytes)": 0,
        "EstimateNs": "",
        "EstimateMs": "",
        "TotalRuntime(s)": 0,
        "CompileTime(s)": f"{compile_time:.6f}",
        "BenchName": bench_name,
        "BenchGroup": "",
        "FunctionName": "",
        "Parameter": "",
        "Arch": "",
        "Status": status,
        "Message": message,
    }


def measure_combination(combo, runs, bench_name, sample_size, measurement_time, warm_up_time, noplot, case_filter, logf):
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
    msg3 = f"[Bench] {bench_name} sample_size={sample_size} measurement_time={measurement_time} warm_up_time={warm_up_time} noplot={noplot}"
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
        results.append(make_failure_row(name, llvm_pass, mir_pass, bench_name, compile_time, status, "build failed"))
        return results

    exe_path = find_bench_exe(bench_name)
    if not exe_path:
        results.append(make_failure_row(name, llvm_pass, mir_pass, bench_name, compile_time, "NoBinary", "bench executable not found"))
        return results

    try:
        size = os.path.getsize(exe_path)
    except Exception:
        size = 0

    for run_id in range(1, runs + 1):
        run_msg = f"[Exp] {name} Iteration {run_id}/{runs}"
        print(run_msg)
        logf.write(run_msg + "\n")
        logf.flush()

        returncode, wall_time, output = run_benchmark(
            exe_path,
            env,
            sample_size,
            measurement_time,
            warm_up_time,
            noplot,
        )
        if output.strip():
            logf.write(output.rstrip() + "\n")
            logf.flush()

        if returncode != 0:
            results.append(
                {
                    "ConfigName": name,
                    "Variant": BENCH_VARIANT,
                    "RunID": run_id,
                    "LLVM_Pass": llvm_pass,
                    "MIR_Pass": mir_pass,
                    "BinarySize(Bytes)": size,
                    "EstimateNs": "",
                    "EstimateMs": "",
                    "TotalRuntime(s)": f"{wall_time:.6f}",
                    "CompileTime(s)": f"{compile_time:.6f}",
                    "BenchName": bench_name,
                    "BenchGroup": "",
                    "FunctionName": "",
                    "Parameter": "",
                    "Arch": "",
                    "Status": "RunFailed",
                    "Message": "bench process exited with non-zero status",
                }
            )
            break

        estimate_rows = collect_estimates_from_output(output, bench_name, case_filter)
        if not estimate_rows:
            results.append(
                {
                    "ConfigName": name,
                    "Variant": BENCH_VARIANT,
                    "RunID": run_id,
                    "LLVM_Pass": llvm_pass,
                    "MIR_Pass": mir_pass,
                    "BinarySize(Bytes)": size,
                    "EstimateNs": "",
                    "EstimateMs": "",
                    "TotalRuntime(s)": f"{wall_time:.6f}",
                    "CompileTime(s)": f"{compile_time:.6f}",
                    "BenchName": bench_name,
                    "BenchGroup": "",
                    "FunctionName": "",
                    "Parameter": "",
                    "Arch": "",
                    "Status": "NoParsedResults",
                    "Message": "benchmark stdout did not contain a parsable markdown result table",
                }
            )
            continue

        for estimate_row in estimate_rows:
            results.append(
                {
                    "ConfigName": name,
                    "Variant": BENCH_VARIANT,
                    "RunID": run_id,
                    "LLVM_Pass": llvm_pass,
                    "MIR_Pass": mir_pass,
                    "BinarySize(Bytes)": size,
                    "EstimateNs": estimate_row["EstimateNs"],
                    "EstimateMs": estimate_row["EstimateMs"],
                    "TotalRuntime(s)": f"{wall_time:.6f}",
                    "CompileTime(s)": f"{compile_time:.6f}",
                    "BenchName": bench_name,
                    "BenchGroup": estimate_row["BenchGroup"],
                    "FunctionName": estimate_row["FunctionName"],
                    "Parameter": estimate_row["Parameter"],
                    "Arch": estimate_row["Arch"],
                    "Status": "Success",
                    "Message": "",
                }
            )

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", nargs="?", default=DEFAULT_JSON_PATH)
    parser.add_argument("--json-path", default="")
    parser.add_argument("--runs", type=int, default=6)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--start-exp", default="")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--bench-name", default="bench_resize")
    parser.add_argument("--case-filter", default="")
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument("--measurement-time", type=float, default=0.0)
    parser.add_argument("--warm-up-time", type=float, default=0.0)
    parser.add_argument("--plot", action="store_true")
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
                    "EstimateNs",
                    "EstimateMs",
                    "TotalRuntime(s)",
                    "CompileTime(s)",
                    "BenchName",
                    "BenchGroup",
                    "FunctionName",
                    "Parameter",
                    "Arch",
                    "Status",
                    "Message",
                ],
            )
            writer.writeheader()
            outcsv.flush()

            for combo in combos:
                rows = measure_combination(
                    combo,
                    args.runs,
                    args.bench_name,
                    args.sample_size,
                    args.measurement_time,
                    args.warm_up_time,
                    not args.plot,
                    args.case_filter.strip(),
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
                "BenchName",
                "BenchGroup",
                "FunctionName",
                "Parameter",
                "n",
                "estimate_ns_mean",
                "estimate_ns_med",
                "estimate_ns_iqr",
                "estimate_ms_mean",
                "estimate_ms_med",
                "estimate_ms_iqr",
                "wall_mean",
                "wall_med",
                "wall_iqr",
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
                "BenchName",
                "BenchGroup",
                "FunctionName",
                "Parameter",
                "n",
                "estimate_ns_mean",
                "estimate_ns_med",
                "estimate_ns_iqr",
                "estimate_ns_iqr_ratio",
                "estimate_ms_mean",
                "estimate_ms_med",
                "estimate_ms_iqr",
                "wall_mean",
                "wall_med",
                "wall_iqr",
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

    inter = compute_interaction(summary, "estimate_ns_med", smaller_is_better=True)
    if inter:
        with open(inter_csv, "w", encoding="utf-8", newline="") as outcsv:
            writer = csv.DictWriter(
                outcsv,
                fieldnames=[
                    "Variant",
                    "BenchName",
                    "BenchGroup",
                    "FunctionName",
                    "Parameter",
                    "metric",
                    "delta",
                    "M_on_L_on",
                    "M_on_L_off",
                    "M_off_L_on",
                    "M_off_L_off",
                ],
            )
            writer.writeheader()
            for row in inter:
                writer.writerow(row)

    print(base_out)


if __name__ == "__main__":
    main()
