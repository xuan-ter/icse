"""
功能：执行基于随机配置的 MIR 与 LLVM Pass 联合实验
输入：JSON 配置文件（包含生成的 Pass 开关组合）
输出：CSV 格式的实验结果与汇总统计（包括二进制大小、运行时、编译时等指标）
描述：
    该脚本读取预先生成的随机配置（JSON），根据配置在编译时禁用指定的 MIR 和 LLVM Passes。
    它负责驱动 cargo build 和 cargo run，测量并记录每个配置的性能指标。
    支持多次重复运行（--runs）以获取稳定的性能数据。
"""
import argparse
import csv
import json
import os
import re
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime
from statistics import mean, median

# Configuration
PROJECT_ROOT = "/root/MIR_LLVM/serde"
DEFAULT_SEARCH_SPACE = "/root/MIR_LLVM/table/table_json/combined_experiment_matrix.json"
DEFAULT_RESULTS_ROOT = os.path.join(PROJECT_ROOT, "results_expanded")
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BENCH_VARIANT = "serde"

BINARY_PATH = os.path.join(PROJECT_ROOT, "target", "release", "serde_test")
ITERATIONS = "2500"

# Global variables for logging, initialized in main/setup
LOG_PATH = ""


def log(message):
    print(message)
    if LOG_PATH:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(message + "\n")


def setup_environment(custom_output_dir=None):
    global LOG_PATH

    base_dir = custom_output_dir or os.path.join(DEFAULT_RESULTS_ROOT, TIMESTAMP)
    os.makedirs(base_dir, exist_ok=True)

    LOG_PATH = os.path.join(base_dir, "experiment_execution.log")
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("Experiment Execution Log\n")
        f.write("========================================\n")

    return {
        "base_dir": base_dir,
        "results_csv": os.path.join(base_dir, "experiment_results.csv"),
        "summary_csv": os.path.join(base_dir, "summary_medians.csv"),
        "volatility_csv": os.path.join(base_dir, "volatility_summary.csv"),
        "interaction_csv": os.path.join(base_dir, "interaction_delta.csv"),
    }


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


def run_command(command, env=None, cwd=PROJECT_ROOT):
    try:
        log(f"[EXEC] {command}")
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            if result.stdout:
                log(f"[STDOUT] {result.stdout.strip()}")
            if result.stderr:
                log(f"[STDERR] {result.stderr.strip()}")
        return result
    except Exception as exc:
        log(f"[ERROR] {exc}")
        return None


def clean_project(env=None):
    target_dir = os.path.join(PROJECT_ROOT, "target")
    if os.path.exists(target_dir):
        try:
            shutil.rmtree(target_dir)
        except Exception:
            if env is None:
                env = os.environ.copy()
            subprocess.run(
                ["cargo", "clean"],
                cwd=PROJECT_ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def parse_duration(text):
    match = re.search(r"took:\s+([0-9\.]+)(s|ms|µs|ns)", text)
    if not match:
        return 0.0
    value = float(match.group(1))
    unit = match.group(2)
    if unit == "s":
        return value
    if unit == "ms":
        return value / 1000.0
    if unit == "µs":
        return value / 1_000_000.0
    if unit == "ns":
        return value / 1_000_000_000.0
    return 0.0


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
    grouped = defaultdict(list)
    for row in rows:
        if row.get("Status") != "Success":
            continue
        key = (row.get("Variant", BENCH_VARIANT), row["ConfigName"])
        grouped[key].append(row)

    output_rows = []
    for (variant, config_name), group_rows in sorted(grouped.items()):
        def values(key, cast=float):
            items = []
            for row in group_rows:
                try:
                    items.append(cast(row[key]))
                except Exception:
                    pass
            return sorted(items)

        def avg_value(key, cast=float):
            items = values(key, cast)
            return mean(items) if items else None

        def med_value(key, cast=float):
            items = values(key, cast)
            return median(items) if items else None

        def iqr_value(key, cast=float):
            items = values(key, cast)
            if not items:
                return None
            q1 = percentile(items, 0.25)
            q3 = percentile(items, 0.75)
            if q1 is None or q3 is None:
                return None
            return q3 - q1

        output_rows.append(
            {
                "Variant": variant,
                "ConfigName": config_name,
                "n": str(len(group_rows)),
                "runtime_mean": f"{avg_value('TotalRuntime(s)'):.6f}" if avg_value("TotalRuntime(s)") is not None else "",
                "runtime_med": f"{med_value('TotalRuntime(s)'):.6f}" if med_value("TotalRuntime(s)") is not None else "",
                "runtime_iqr": f"{iqr_value('TotalRuntime(s)'):.6f}" if iqr_value("TotalRuntime(s)") is not None else "",
                "compile_mean": f"{avg_value('CompileTime(s)'):.6f}" if avg_value("CompileTime(s)") is not None else "",
                "compile_med": f"{med_value('CompileTime(s)'):.6f}" if med_value("CompileTime(s)") is not None else "",
                "compile_iqr": f"{iqr_value('CompileTime(s)'):.6f}" if iqr_value("CompileTime(s)") is not None else "",
                "size_mean": f"{avg_value('BinarySize(Bytes)', int):.6f}" if avg_value("BinarySize(Bytes)", int) is not None else "",
                "size_med": f"{med_value('BinarySize(Bytes)', int):.0f}" if med_value("BinarySize(Bytes)", int) is not None else "",
            }
        )
    return output_rows


def compute_interaction(summary_rows, metric_key, smaller_is_better=True):
    indexed = {(row["Variant"], row["ConfigName"]): row for row in summary_rows}
    output_rows = []
    for variant in sorted({row["Variant"] for row in summary_rows}):
        def get_value(config_name):
            row = indexed.get((variant, config_name))
            if not row:
                return None
            value = row.get(metric_key, "")
            if value == "":
                return None
            try:
                return float(value)
            except Exception:
                return None

        a = get_value("M_on_L_on")
        b = get_value("M_on_L_off")
        c = get_value("M_off_L_on")
        d = get_value("M_off_L_off")
        if None in (a, b, c, d):
            continue

        effect = (lambda x: -x) if smaller_is_better else (lambda x: x)
        delta = effect(a) - effect(b) - effect(c) + effect(d)
        output_rows.append(
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
    return output_rows


def build_volatility_summary(summary_rows):
    def as_float(value):
        if value in ("", None):
            return None
        try:
            return float(value)
        except Exception:
            return None

    output_rows = []
    for row in summary_rows:
        runtime_med = as_float(row.get("runtime_med"))
        runtime_iqr = as_float(row.get("runtime_iqr"))
        compile_med = as_float(row.get("compile_med"))
        compile_iqr = as_float(row.get("compile_iqr"))

        runtime_iqr_ratio = None
        if runtime_med not in (None, 0.0) and runtime_iqr is not None:
            runtime_iqr_ratio = runtime_iqr / runtime_med

        compile_iqr_ratio = None
        if compile_med not in (None, 0.0) and compile_iqr is not None:
            compile_iqr_ratio = compile_iqr / compile_med

        output_rows.append(
            {
                "Variant": row["Variant"],
                "ConfigName": row["ConfigName"],
                "n": row["n"],
                "runtime_mean": row["runtime_mean"],
                "runtime_med": row["runtime_med"],
                "runtime_iqr": row["runtime_iqr"],
                "runtime_iqr_ratio": f"{runtime_iqr_ratio:.6f}" if runtime_iqr_ratio is not None else "",
                "compile_mean": row["compile_mean"],
                "compile_med": row["compile_med"],
                "compile_iqr": row["compile_iqr"],
                "compile_iqr_ratio": f"{compile_iqr_ratio:.6f}" if compile_iqr_ratio is not None else "",
                "size_mean": row["size_mean"],
                "size_med": row["size_med"],
            }
        )

    def sort_key(row):
        runtime_ratio = as_float(row["runtime_iqr_ratio"])
        runtime_iqr = as_float(row["runtime_iqr"])
        compile_ratio = as_float(row["compile_iqr_ratio"])
        compile_iqr = as_float(row["compile_iqr"])
        return (
            runtime_ratio if runtime_ratio is not None else -1.0,
            runtime_iqr if runtime_iqr is not None else -1.0,
            compile_ratio if compile_ratio is not None else -1.0,
            compile_iqr if compile_iqr is not None else -1.0,
            row["Variant"],
            row["ConfigName"],
        )

    output_rows.sort(key=sort_key, reverse=True)
    return output_rows


def measure_combination(combo, runs=1, skip_clean=False, warmup=1):
    name = combo.get("name") or combo.get("Experiment_ID") or "Unknown"

    llvm_data = combo.get("llvm")
    mir_data = combo.get("mir")

    llvm_pass = llvm_data["pass"] if llvm_data else "None"
    llvm_switches = llvm_data["switches"] if llvm_data and "switches" in llvm_data else []

    mir_pass = mir_data["pass"] if mir_data else "None"
    mir_switches = mir_data["switches"] if mir_data and "switches" in mir_data else []

    llvm_args = []
    for switch in llvm_switches:
        llvm_args.append(f"-C llvm-args={switch}")

    mir_args = []
    for switch in mir_switches:
        mir_args.append(f"-Z mir-enable-passes={switch}")

    rustflags_parts = ["-C opt-level=3"] + llvm_args + mir_args
    rustflags = " ".join(rustflags_parts)

    env = os.environ.copy()
    env["RUSTFLAGS"] = rustflags

    cargo_bin = os.path.expanduser("~/.cargo/bin")
    if cargo_bin not in env.get("PATH", ""):
        env["PATH"] = f"{cargo_bin}:{env.get('PATH', '')}"

    results = []
    log(f"[Exp] {name}")
    log(f"[Flags] {rustflags}")

    if not skip_clean:
        clean_project(env)

    start_compile = datetime.now()
    build_res = run_command("cargo build --release --quiet", env=env)
    compile_duration = (datetime.now() - start_compile).total_seconds()

    if not build_res or build_res.returncode != 0:
        log("  Build Failed")
        results.append(
            {
                "ConfigName": name,
                "Variant": BENCH_VARIANT,
                "RunID": 1,
                "LLVM_Pass": llvm_pass,
                "MIR_Pass": mir_pass,
                "BinarySize(Bytes)": 0,
                "TotalRuntime(s)": "0.000000",
                "CompileTime(s)": f"{compile_duration:.6f}",
                "Status": "BuildFailed",
            }
        )
        return results

    if not os.path.exists(BINARY_PATH):
        log("  Binary missing")
        results.append(
            {
                "ConfigName": name,
                "Variant": BENCH_VARIANT,
                "RunID": 1,
                "LLVM_Pass": llvm_pass,
                "MIR_Pass": mir_pass,
                "BinarySize(Bytes)": 0,
                "TotalRuntime(s)": "0.000000",
                "CompileTime(s)": f"{compile_duration:.6f}",
                "Status": "NoBinary",
            }
        )
        return results

    size_bytes = os.path.getsize(BINARY_PATH)

    for run_id in range(1, runs + 1):
        log(f"[Measure] {name} Run {run_id}/{runs}")

        for warmup_id in range(max(warmup, 0)):
            warmup_res = run_command(f"{BINARY_PATH} {ITERATIONS}")
            if not warmup_res or warmup_res.returncode != 0:
                log(f"  Warmup Failed ({warmup_id + 1}/{warmup})")
                results.append(
                    {
                        "ConfigName": name,
                        "Variant": BENCH_VARIANT,
                        "RunID": run_id,
                        "LLVM_Pass": llvm_pass,
                        "MIR_Pass": mir_pass,
                        "BinarySize(Bytes)": size_bytes,
                        "TotalRuntime(s)": "0.000000",
                        "CompileTime(s)": f"{compile_duration:.6f}",
                        "Status": "WarmupFailed",
                    }
                )
                break
        else:
            run_res = run_command(f"{BINARY_PATH} {ITERATIONS}")

            ser_time = 0.0
            de_time = 0.0
            total_time = 0.0
            status = "RunFailed"

            if run_res and run_res.returncode == 0:
                ser_match = re.search(r"Serialize Time:\s+([0-9\.]+)\s*s", run_res.stdout)
                if ser_match:
                    ser_time = float(ser_match.group(1))
                else:
                    ser_match = re.search(r"Serialization took:\s+(.+)", run_res.stdout)
                    if ser_match:
                        ser_time = parse_duration("took: " + ser_match.group(1))

                de_match = re.search(r"Deserialize Time:\s+([0-9\.]+)\s*s", run_res.stdout)
                if de_match:
                    de_time = float(de_match.group(1))
                else:
                    de_match = re.search(r"Deserialization took:\s+(.+)", run_res.stdout)
                    if de_match:
                        de_time = parse_duration("took: " + de_match.group(1))

                total_time = ser_time + de_time
                status = "Success"
                log(f"[Result] Size={size_bytes}B, Compile={compile_duration:.6f}s, RunTotal={total_time:.6f}s")
            else:
                log("  Runtime Failed")

            results.append(
                {
                    "ConfigName": name,
                    "Variant": BENCH_VARIANT,
                    "RunID": run_id,
                    "LLVM_Pass": llvm_pass,
                    "MIR_Pass": mir_pass,
                    "BinarySize(Bytes)": size_bytes,
                    "TotalRuntime(s)": f"{total_time:.6f}",
                    "CompileTime(s)": f"{compile_duration:.6f}",
                    "Status": status,
                }
            )
            continue

    return results


def main():
    parser = argparse.ArgumentParser(description="Run LLVM/MIR ablation experiment")
    parser.add_argument("config_file", nargs="?", default=DEFAULT_SEARCH_SPACE, help="Path to JSON config file")
    parser.add_argument("--json-path", default="", help="Explicit JSON config path")
    parser.add_argument("--limit", type=int, default=0, help="Only run the first N configurations after start offset")
    parser.add_argument("--start", type=int, default=0, help="Start from the specified configuration index")
    parser.add_argument("--start-exp", default="", help="Start from the specified configuration name")
    parser.add_argument("--out-dir", default="", help="Custom output directory for results")
    parser.add_argument("--output-dir", default="", help="Custom output directory for results")
    parser.add_argument("--runs", type=int, default=10, help="Number of iterations per configuration (Compile + Run)")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup runs before each measured run")
    parser.add_argument("--skip-clean", action="store_true", help="Do not remove target/ between runs/configs")
    args = parser.parse_args()

    config_path = args.json_path.strip() or str(args.config_file)
    if not os.path.exists(config_path):
        raise SystemExit(f"JSON path not found: {config_path}")

    output_dir = args.out_dir.strip() or args.output_dir.strip()
    output_paths = setup_environment(output_dir)

    combinations = get_combinations(config_path)
    start_index = 0
    if args.start_exp.strip():
        found = find_combo_start_index(combinations, args.start_exp.strip())
        if found is None:
            raise SystemExit(f'--start-exp "{args.start_exp.strip()}" not found in combinations')
        start_index = found
    elif args.start > 0:
        start_index = args.start

    if start_index > 0:
        combinations = combinations[start_index:]
    if args.limit and args.limit > 0:
        combinations = combinations[: args.limit]

    log(f"Found {len(combinations)} combinations to test from {config_path}")
    log(f"Running each configuration {args.runs} times")
    log(f"Warmup runs before each measured run: {args.warmup}")
    log(f"Total Rows: {len(combinations)}")

    with open(output_paths["results_csv"], "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "ConfigName",
                "Variant",
                "RunID",
                "LLVM_Pass",
                "MIR_Pass",
                "BinarySize(Bytes)",
                "TotalRuntime(s)",
                "CompileTime(s)",
                "Status",
            ],
        )
        writer.writeheader()
        f.flush()

        for combo in combinations:
            rows = measure_combination(combo, args.runs, skip_clean=args.skip_clean, warmup=args.warmup)
            for row in rows:
                writer.writerow(row)
            f.flush()

    results_rows = []
    with open(output_paths["results_csv"], "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results_rows.append(row)

    summary_rows = aggregate_summary(results_rows)
    with open(output_paths["summary_csv"], "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "Variant",
                "ConfigName",
                "n",
                "runtime_mean",
                "runtime_med",
                "runtime_iqr",
                "compile_mean",
                "compile_med",
                "compile_iqr",
                "size_mean",
                "size_med",
            ],
        )
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(row)

    volatility_rows = build_volatility_summary(summary_rows)
    with open(output_paths["volatility_csv"], "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "Variant",
                "ConfigName",
                "n",
                "runtime_mean",
                "runtime_med",
                "runtime_iqr",
                "runtime_iqr_ratio",
                "compile_mean",
                "compile_med",
                "compile_iqr",
                "compile_iqr_ratio",
                "size_mean",
                "size_med",
            ],
        )
        writer.writeheader()
        for row in volatility_rows:
            writer.writerow(row)

    interaction_rows = compute_interaction(summary_rows, "runtime_med", smaller_is_better=True)
    if interaction_rows:
        with open(output_paths["interaction_csv"], "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["Variant", "metric", "delta", "M_on_L_on", "M_on_L_off", "M_off_L_on", "M_off_L_off"],
            )
            writer.writeheader()
            for row in interaction_rows:
                writer.writerow(row)

    log("Experiment Completed.")
    print(output_paths["base_dir"])


if __name__ == "__main__":
    main()
