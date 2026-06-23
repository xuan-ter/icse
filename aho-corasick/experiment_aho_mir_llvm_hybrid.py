import argparse
import csv
import glob
import json
import os
import re
import shutil
import subprocess
import time
import tomllib
from collections import defaultdict
from datetime import datetime
from math import ceil
from statistics import mean, median


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

PROJECT_ROOT = SCRIPT_DIR
ENGINE_DIR = os.path.join(PROJECT_ROOT, "benchmarks", "engines", "rust-aho-corasick")
ENGINE_CARGO_TOML = os.path.join(ENGINE_DIR, "Cargo.toml")
BINARY_PATH = os.path.join(ENGINE_DIR, "target", "release", "main")
DEFAULT_JSON_PATH = os.path.join(REPO_ROOT, "table", "table_json", "combined_experiment_matrix.json")
DEFAULT_RESULTS_ROOT = os.path.join(PROJECT_ROOT, "results")
DEFAULT_BENCH_DEF = os.path.join(PROJECT_ROOT, "benchmarks", "definitions", "sherlock.toml")
DEFAULT_BENCH_NAME = "words5000"
DEFAULT_ENGINE = "default/standard"


def bench_build_cmd(quiet=False):
    cmd = ["cargo", "+nightly", "build", "--release"]
    if quiet:
        cmd.append("--quiet")
    return cmd


def get_combinations(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("combinations", [])


def resolve_json_path(json_arg):
    candidate = (json_arg or "").strip()
    if not candidate:
        return DEFAULT_JSON_PATH
    if os.path.isdir(candidate):
        preferred = [
            os.path.join(candidate, "combined_experiment_matrix.json"),
            os.path.join(candidate, "table_json", "combined_experiment_matrix.json"),
        ]
        for path in preferred:
            if os.path.exists(path):
                return path
        matches = sorted(glob.glob(os.path.join(candidate, "**", "*.json"), recursive=True))
        if matches:
            return matches[0]
    return candidate


def find_start_index_by_name(combos, start_name):
    if not start_name:
        return None
    if start_name.upper() in {"BEGIN", "START", "ALL"}:
        return None
    for i, combo in enumerate(combos):
        name = combo.get("name") or combo.get("Experiment_ID")
        if name == start_name:
            return i
    return None


def labels_from_combo(combo):
    mir_pass = "N/A"
    if combo.get("mir"):
        if isinstance(combo["mir"], dict):
            mir_pass = combo["mir"].get("pass", "N/A")
        else:
            mir_pass = str(combo["mir"])

    llvm_pass = "None"
    if combo.get("llvm"):
        if isinstance(combo["llvm"], dict):
            llvm_pass = combo["llvm"].get("pass", "None")
        else:
            llvm_pass = str(combo["llvm"])

    return llvm_pass, mir_pass


def clean_project(env):
    target_dir = os.path.join(ENGINE_DIR, "target")
    if os.path.exists(target_dir):
        try:
            shutil.rmtree(target_dir)
        except Exception:
            subprocess.run(
                ["cargo", "clean"],
                cwd=ENGINE_DIR,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    else:
        subprocess.run(
            ["cargo", "clean"],
            cwd=ENGINE_DIR,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    time.sleep(0.25)


def compose_rustflags_from_combo(combo):
    parts = ["-C opt-level=3"]
    if combo.get("mir") and isinstance(combo["mir"], dict) and combo["mir"].get("switches"):
        switches = ",".join(combo["mir"]["switches"])
        parts.append(f"-Z mir-enable-passes={switches}")
    if combo.get("llvm") and isinstance(combo["llvm"], dict) and combo["llvm"].get("switches"):
        for switch in combo["llvm"]["switches"]:
            parts.append(f"-C llvm-args={switch}")
    if combo.get("RUSTFLAGS"):
        parts.append(str(combo["RUSTFLAGS"]))
    parts.append("-C codegen-units=1")
    parts.append("--emit=llvm-ir,link")
    return " ".join(parts)


def build_project(env, rustflags, logf, retries=2):
    env2 = dict(env)
    env2["RUSTFLAGS"] = rustflags
    env2["CARGO_INCREMENTAL"] = "0"

    backoff = 0.5
    last_err = ""
    t0 = time.perf_counter()
    for _ in range(retries + 1):
        r = subprocess.run(
            bench_build_cmd(quiet=True),
            cwd=ENGINE_DIR,
            env=env2,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if r.returncode == 0:
            t1 = time.perf_counter()
            return True, (t1 - t0), env2, "Success"
        err = r.stderr or ""
        last_err = err
        if logf is not None:
            logf.write(err + "\n")
            logf.flush()
        if ("Text file busy (os error 26)" in err) or ("never executed" in err):
            time.sleep(backoff)
            backoff = min(backoff * 2, 4.0)
            continue
        t1 = time.perf_counter()
        return False, (t1 - t0), env2, "BuildFailed"

    t1 = time.perf_counter()
    if ("Text file busy (os error 26)" in last_err) or ("never executed" in last_err) or (
        "failed to run custom build command" in last_err
    ):
        return False, (t1 - t0), env2, "Skipped"
    return False, (t1 - t0), env2, "BuildFailed"


def newest_llvm_ir_path():
    patterns = [
        os.path.join(ENGINE_DIR, "target", "release", "deps", "main-*.ll"),
        os.path.join(ENGINE_DIR, "target", "release", "deps", "aho_corasick-*.ll"),
        os.path.join(ENGINE_DIR, "target", "release", "deps", "shared-*.ll"),
    ]
    candidates = []
    for pattern in patterns:
        candidates.extend(glob.glob(pattern))
    if not candidates:
        return ""
    candidates = sorted(set(candidates), key=lambda path: os.path.getmtime(path), reverse=True)
    return candidates[0]


def count_llvm_ir_metrics(ll_path):
    metrics = {
        "IR_alloca": 0,
        "IR_load": 0,
        "IR_store": 0,
        "IR_gep": 0,
        "IR_phi": 0,
        "IR_bb": 0,
    }
    if not ll_path or not os.path.exists(ll_path):
        return metrics
    with open(ll_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            if " alloca " in line:
                metrics["IR_alloca"] += 1
            if re.search(r"\bload\b", line):
                metrics["IR_load"] += 1
            if re.search(r"\bstore\b", line):
                metrics["IR_store"] += 1
            if "getelementptr" in line:
                metrics["IR_gep"] += 1
            if re.search(r"\bphi\b", line):
                metrics["IR_phi"] += 1
            if stripped.endswith(":") and not stripped.startswith(";") and "!" not in stripped:
                metrics["IR_bb"] += 1
    return metrics


def get_exe_path():
    return BINARY_PATH if os.path.exists(BINARY_PATH) else None


def resolve_bench_resource(def_dir, path_value, category):
    candidates = [
        os.path.join(def_dir, path_value),
        os.path.join(PROJECT_ROOT, "benchmarks", category, path_value),
        os.path.join(PROJECT_ROOT, "benchmarks", path_value),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(f"Could not resolve benchmark resource: {path_value}")


def load_needles(def_dir, regex_field):
    if isinstance(regex_field, list):
        return [str(item) for item in regex_field]
    if isinstance(regex_field, dict):
        path_value = regex_field.get("path", "")
        per_line = regex_field.get("per-line", "")
        if not path_value or per_line != "pattern":
            raise ValueError("Only regex = { path = ..., per-line = 'pattern' } is supported")
        regex_path = resolve_bench_resource(def_dir, path_value, "regexes")
        needles = []
        with open(regex_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.rstrip("\r\n")
                if line:
                    needles.append(line)
        return needles
    raise ValueError("Unsupported regex benchmark field")


def load_haystack(def_dir, haystack_field):
    if isinstance(haystack_field, str):
        return haystack_field.encode("utf-8")
    if isinstance(haystack_field, dict):
        path_value = haystack_field.get("path", "")
        if not path_value:
            raise ValueError("Haystack path is empty")
        haystack_path = resolve_bench_resource(def_dir, path_value, "haystacks")
        with open(haystack_path, "rb") as f:
            return f.read()
    raise ValueError("Unsupported haystack benchmark field")


def klv_item(key, value_bytes):
    return key.encode("utf-8") + b":" + str(len(value_bytes)).encode("utf-8") + b":" + value_bytes + b"\n"


def build_benchmark_payload(definition_path, bench_name, max_iters=1, max_warmup_iters=0, max_time_ns=10_000_000_000):
    with open(definition_path, "rb") as f:
        data = tomllib.load(f)
    benches = data.get("bench", [])
    if not benches:
        raise ValueError(f"No benchmark entries found in {definition_path}")

    selected = None
    for bench in benches:
        if bench.get("name") == bench_name:
            selected = bench
            break
    if selected is None:
        available = ", ".join(sorted(str(bench.get("name", "")) for bench in benches))
        raise ValueError(f"Benchmark {bench_name!r} not found. Available: {available}")

    def_dir = os.path.dirname(definition_path)
    needles = load_needles(def_dir, selected.get("regex", []))
    haystack = load_haystack(def_dir, selected.get("haystack", ""))
    payload = bytearray()
    payload += klv_item("name", str(selected.get("name", "")).encode("utf-8"))
    payload += klv_item("model", str(selected.get("model", "count")).encode("utf-8"))
    for needle in needles:
        payload += klv_item("pattern", needle.encode("utf-8"))
    payload += klv_item("haystack", haystack)
    payload += klv_item("case-insensitive", str(bool(selected.get("case-insensitive", False))).lower().encode("utf-8"))
    payload += klv_item("unicode", str(bool(selected.get("unicode", False))).lower().encode("utf-8"))
    payload += klv_item("max-iters", str(int(max_iters)).encode("utf-8"))
    payload += klv_item("max-warmup-iters", str(int(max_warmup_iters)).encode("utf-8"))
    payload += klv_item("max-time", str(int(max_time_ns)).encode("utf-8"))
    payload += klv_item("max-warmup-time", b"0")
    return bytes(payload)


def run_benchmark_once(exe_path, engine, payload):
    p = subprocess.run(
        [exe_path, engine],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
    )
    if p.returncode != 0:
        err = (p.stderr or p.stdout or b"RunFailed")[:2000]
        return None, err.decode("utf-8", errors="ignore")

    lines = [line.strip() for line in (p.stdout or b"").decode("utf-8", errors="ignore").splitlines() if line.strip()]
    if not lines:
        return None, "No benchmark samples were produced"
    sample = lines[-1]
    parts = sample.split(",", 1)
    if len(parts) != 2:
        return None, f"Unexpected benchmark output: {sample}"
    try:
        duration_ns = int(parts[0].strip())
    except Exception:
        return None, f"Invalid duration output: {sample}"
    return float(duration_ns) / 1_000_000_000.0, ""


def run_benchmark_repeated(exe_path, engine, payload, repeats):
    repeats = int(repeats) if repeats is not None else 1
    repeats = max(1, repeats)
    total = 0.0
    for _ in range(repeats):
        elapsed, err = run_benchmark_once(exe_path, engine, payload)
        if elapsed is None:
            return None, err
        total += elapsed
    return total, ""


def pick_baseline_combo(combos):
    for combo in combos:
        name = combo.get("name") or combo.get("Experiment_ID") or ""
        if name == "EXP_DBL_000_BASELINE":
            return combo
    for combo in combos:
        name = combo.get("name") or combo.get("Experiment_ID") or ""
        if name == "EXP_000_ALL_OFF":
            return combo
    return combos[0] if combos else None


def calibrate_repeats(env_base, baseline_combo, engine, payload, target_seconds, max_repeats, skip_clean, logf):
    if not baseline_combo:
        return 15
    if target_seconds is None or float(target_seconds) <= 0:
        return 15

    rustflags = compose_rustflags_from_combo(baseline_combo)
    if not skip_clean:
        clean_project(env_base)
    ok, _, _, status = build_project(env_base, rustflags, logf)
    if not ok:
        if logf is not None:
            logf.write(f"[Calibrate] baseline build failed with status={status}\n")
            logf.flush()
        return 1

    exe_path = get_exe_path()
    if not exe_path:
        return 1

    elapsed, _ = run_benchmark_once(exe_path, engine, payload)
    if elapsed is None or elapsed <= 0:
        return 1
    repeats = int(ceil(float(target_seconds) / float(elapsed)))
    return max(1, min(int(max_repeats), repeats))


def aggregate_summary(rows):
    by = defaultdict(list)
    for row in rows:
        key = (row["Variant"], row["ConfigName"])
        if row["Status"] != "Success":
            continue
        by[key].append(row)

    out = []
    for (variant, config_name), grouped_rows in sorted(by.items()):
        def values(key, cast=float):
            parsed = []
            for row in grouped_rows:
                try:
                    parsed.append(cast(row[key]))
                except Exception:
                    pass
            return sorted(parsed)

        def meds(key, cast=float):
            parsed = values(key, cast)
            return median(parsed) if parsed else None

        def avgs(key, cast=float):
            parsed = values(key, cast)
            return mean(parsed) if parsed else None

        def percentile(parsed, p):
            if not parsed:
                return None
            if len(parsed) == 1:
                return float(parsed[0])
            pos = (len(parsed) - 1) * p
            lo = int(pos)
            hi = min(lo + 1, len(parsed) - 1)
            frac = pos - lo
            return float(parsed[lo]) * (1.0 - frac) + float(parsed[hi]) * frac

        def iqr(key, cast=float):
            parsed = values(key, cast)
            if not parsed:
                return None
            q1 = percentile(parsed, 0.25)
            q3 = percentile(parsed, 0.75)
            if q1 is None or q3 is None:
                return None
            return q3 - q1

        out.append(
            {
                "Variant": variant,
                "ConfigName": config_name,
                "n": str(len(grouped_rows)),
                "runtime_mean": f"{avgs('TotalRuntime(s)'):.6f}" if avgs("TotalRuntime(s)") is not None else "",
                "runtime_med": f"{meds('TotalRuntime(s)'):.6f}" if meds("TotalRuntime(s)") is not None else "",
                "runtime_iqr": f"{iqr('TotalRuntime(s)'):.6f}" if iqr("TotalRuntime(s)") is not None else "",
                "compile_mean": f"{avgs('CompileTime(s)'):.6f}" if avgs("CompileTime(s)") is not None else "",
                "compile_med": f"{meds('CompileTime(s)'):.6f}" if meds("CompileTime(s)") is not None else "",
                "compile_iqr": f"{iqr('CompileTime(s)'):.6f}" if iqr("CompileTime(s)") is not None else "",
                "size_mean": f"{avgs('BinarySize(Bytes)', int):.6f}" if avgs("BinarySize(Bytes)", int) is not None else "",
                "size_med": f"{meds('BinarySize(Bytes)', int):.0f}" if meds("BinarySize(Bytes)", int) is not None else "",
                "alloca_mean": f"{avgs('IR_alloca', int):.6f}" if avgs("IR_alloca", int) is not None else "",
                "alloca_med": f"{meds('IR_alloca', int):.0f}" if meds("IR_alloca", int) is not None else "",
                "load_mean": f"{avgs('IR_load', int):.6f}" if avgs("IR_load", int) is not None else "",
                "load_med": f"{meds('IR_load', int):.0f}" if meds("IR_load", int) is not None else "",
                "store_mean": f"{avgs('IR_store', int):.6f}" if avgs("IR_store", int) is not None else "",
                "store_med": f"{meds('IR_store', int):.0f}" if meds("IR_store", int) is not None else "",
                "gep_mean": f"{avgs('IR_gep', int):.6f}" if avgs("IR_gep", int) is not None else "",
                "gep_med": f"{meds('IR_gep', int):.0f}" if meds("IR_gep", int) is not None else "",
                "phi_mean": f"{avgs('IR_phi', int):.6f}" if avgs("IR_phi", int) is not None else "",
                "phi_med": f"{meds('IR_phi', int):.0f}" if meds("IR_phi", int) is not None else "",
                "bb_mean": f"{avgs('IR_bb', int):.6f}" if avgs("IR_bb", int) is not None else "",
                "bb_med": f"{meds('IR_bb', int):.0f}" if meds("IR_bb", int) is not None else "",
            }
        )
    return out


def compute_interaction(summary_rows, metric_key, smaller_is_better=True):
    index = {(row["Variant"], row["ConfigName"]): row for row in summary_rows}
    out = []
    for variant in sorted({row["Variant"] for row in summary_rows}):
        def get(config_name):
            row = index.get((variant, config_name))
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

        out.append(
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

    out.sort(key=sort_key, reverse=True)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", nargs="?", default=DEFAULT_JSON_PATH)
    parser.add_argument("--json-path", default="")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--target-seconds", type=float, default=0)
    parser.add_argument("--max-repeats", type=int, default=2000)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--skip-clean", action="store_true")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start-name", default="")
    parser.add_argument("--bench-definition", default=DEFAULT_BENCH_DEF)
    parser.add_argument("--bench-name", default=DEFAULT_BENCH_NAME)
    parser.add_argument("--engine", default=DEFAULT_ENGINE)
    args = parser.parse_args()

    payload = build_benchmark_payload(args.bench_definition, args.bench_name)
    variant_name = f"{args.bench_name}:{args.engine.replace('/', '_')}"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = (
        args.out_dir.strip()
        or args.output_dir.strip()
        or os.path.join(DEFAULT_RESULTS_ROOT, f"run_{ts}")
    )
    os.makedirs(out_dir, exist_ok=True)

    results_csv = os.path.join(out_dir, "experiment_results.csv")
    summary_csv = os.path.join(out_dir, "summary_medians.csv")
    inter_csv = os.path.join(out_dir, "interaction_delta.csv")
    volatility_csv = os.path.join(out_dir, "volatility_summary.csv")
    exec_log = os.path.join(out_dir, "experiment_execution.log")

    config_path = resolve_json_path(args.json_path.strip() or str(args.config_file))
    combos = get_combinations(config_path)

    start_idx = find_start_index_by_name(combos, args.start_name)
    if start_idx is not None:
        combos = combos[start_idx:]

    start = max(int(args.start), 0)
    if int(args.limit) > 0:
        combos = combos[start : start + int(args.limit)]
    else:
        combos = combos[start:]

    env_base = os.environ.copy()
    cargo_bin = os.path.expanduser("~/.cargo/bin")
    if cargo_bin and cargo_bin not in env_base.get("PATH", ""):
        env_base["PATH"] = f"{cargo_bin}:{env_base.get('PATH', '')}"

    baseline_combo = pick_baseline_combo(combos)

    with open(exec_log, "w", encoding="utf-8") as logf:
        logf.write(f"Total Rows: {len(combos)}\n")
        logf.write(f"[Benchmark] definition={args.bench_definition} name={args.bench_name} engine={args.engine}\n")
        logf.flush()

        run_repeats = calibrate_repeats(
            env_base=env_base,
            baseline_combo=baseline_combo,
            engine=args.engine,
            payload=payload,
            target_seconds=args.target_seconds,
            max_repeats=args.max_repeats,
            skip_clean=args.skip_clean,
            logf=logf,
        )

        fields = [
            "ConfigName",
            "Variant",
            "RunID",
            "LLVM_Pass",
            "MIR_Pass",
            "BinarySize(Bytes)",
            "TotalRuntime(s)",
            "CompileTime(s)",
            "IR_alloca",
            "IR_load",
            "IR_store",
            "IR_gep",
            "IR_phi",
            "IR_bb",
            "LLVM_IR_Path",
            "RunRepeats",
            "TargetSeconds",
            "Status",
        ]

        with open(results_csv, "w", encoding="utf-8", newline="") as outcsv:
            writer = csv.DictWriter(outcsv, fieldnames=fields)
            writer.writeheader()

            for combo in combos:
                name = combo.get("name") or combo.get("Experiment_ID") or "Unknown"
                llvm_pass, mir_pass = labels_from_combo(combo)
                rustflags = compose_rustflags_from_combo(combo)
                warmup_count = max(args.warmup, 0)
                run_count = max(args.runs, 1)

                msg1 = f"[Build] {name}"
                msg2 = f"[Flags] {rustflags}"
                print(msg1)
                print(msg2)
                logf.write(msg1 + "\n")
                logf.write(msg2 + "\n")
                logf.flush()

                if not args.skip_clean:
                    clean_project(env_base)

                ok, compile_time, _, status = build_project(env_base, rustflags, logf)
                if not ok:
                    for run_id in range(1, run_count + 1):
                        writer.writerow(
                            {
                                "ConfigName": name,
                                "Variant": variant_name,
                                "RunID": run_id,
                                "LLVM_Pass": llvm_pass,
                                "MIR_Pass": mir_pass,
                                "BinarySize(Bytes)": 0,
                                "TotalRuntime(s)": 0,
                                "CompileTime(s)": f"{compile_time:.6f}",
                                "IR_alloca": "",
                                "IR_load": "",
                                "IR_store": "",
                                "IR_gep": "",
                                "IR_phi": "",
                                "IR_bb": "",
                                "LLVM_IR_Path": "",
                                "RunRepeats": "",
                                "TargetSeconds": "",
                                "Status": status,
                            }
                        )
                    outcsv.flush()
                    continue

                exe_path = get_exe_path()
                if not exe_path:
                    for run_id in range(1, run_count + 1):
                        writer.writerow(
                            {
                                "ConfigName": name,
                                "Variant": variant_name,
                                "RunID": run_id,
                                "LLVM_Pass": llvm_pass,
                                "MIR_Pass": mir_pass,
                                "BinarySize(Bytes)": 0,
                                "TotalRuntime(s)": 0,
                                "CompileTime(s)": f"{compile_time:.6f}",
                                "IR_alloca": "",
                                "IR_load": "",
                                "IR_store": "",
                                "IR_gep": "",
                                "IR_phi": "",
                                "IR_bb": "",
                                "LLVM_IR_Path": "",
                                "RunRepeats": "",
                                "TargetSeconds": "",
                                "Status": "NoBinary",
                            }
                        )
                    outcsv.flush()
                    continue

                size = os.path.getsize(exe_path) if os.path.exists(exe_path) else 0
                ll_path = newest_llvm_ir_path()
                ir_metrics = count_llvm_ir_metrics(ll_path)

                warmup_failed = False
                for warmup_id in range(1, warmup_count + 1):
                    warmup_msg = f"[Warmup] {name} Iteration {warmup_id}/{warmup_count}"
                    print(warmup_msg)
                    logf.write(warmup_msg + "\n")
                    logf.flush()
                    wall_time, err = run_benchmark_repeated(exe_path, args.engine, payload, run_repeats)
                    if wall_time is None:
                        print(f"[Warmup] Failed for {name}: {err}")
                        logf.write(f"[Warmup] Failed for {name}: {err}\n")
                        logf.flush()
                        warmup_failed = True
                        break

                if warmup_failed:
                    for run_id in range(1, run_count + 1):
                        writer.writerow(
                            {
                                "ConfigName": name,
                                "Variant": variant_name,
                                "RunID": run_id,
                                "LLVM_Pass": llvm_pass,
                                "MIR_Pass": mir_pass,
                                "BinarySize(Bytes)": size,
                                "TotalRuntime(s)": 0,
                                "CompileTime(s)": f"{compile_time:.6f}",
                                "IR_alloca": ir_metrics["IR_alloca"],
                                "IR_load": ir_metrics["IR_load"],
                                "IR_store": ir_metrics["IR_store"],
                                "IR_gep": ir_metrics["IR_gep"],
                                "IR_phi": ir_metrics["IR_phi"],
                                "IR_bb": ir_metrics["IR_bb"],
                                "LLVM_IR_Path": ll_path,
                                "RunRepeats": run_repeats,
                                "TargetSeconds": f"{args.target_seconds:.6f}",
                                "Status": "RunFailed",
                            }
                        )
                    outcsv.flush()
                    continue

                for run_id in range(1, run_count + 1):
                    run_msg = f"[Exp] {name} Run {run_id}/{run_count}"
                    print(run_msg)
                    logf.write(run_msg + "\n")
                    logf.flush()
                    wall_time, err = run_benchmark_repeated(exe_path, args.engine, payload, run_repeats)
                    if wall_time is None:
                        print(f"[Run] Failed for {name}: {err}")
                        writer.writerow(
                            {
                                "ConfigName": name,
                                "Variant": variant_name,
                                "RunID": run_id,
                                "LLVM_Pass": llvm_pass,
                                "MIR_Pass": mir_pass,
                                "BinarySize(Bytes)": size,
                                "TotalRuntime(s)": 0,
                                "CompileTime(s)": f"{compile_time:.6f}",
                                "IR_alloca": ir_metrics["IR_alloca"],
                                "IR_load": ir_metrics["IR_load"],
                                "IR_store": ir_metrics["IR_store"],
                                "IR_gep": ir_metrics["IR_gep"],
                                "IR_phi": ir_metrics["IR_phi"],
                                "IR_bb": ir_metrics["IR_bb"],
                                "LLVM_IR_Path": ll_path,
                                "RunRepeats": run_repeats,
                                "TargetSeconds": f"{args.target_seconds:.6f}",
                                "Status": "RunFailed",
                            }
                        )
                        outcsv.flush()
                        continue

                    print(f"[Result] Size={size}B, Compile={compile_time:.6f}s, Run={wall_time:.6f}s")
                    writer.writerow(
                        {
                            "ConfigName": name,
                            "Variant": variant_name,
                            "RunID": run_id,
                            "LLVM_Pass": llvm_pass,
                            "MIR_Pass": mir_pass,
                            "BinarySize(Bytes)": size,
                            "TotalRuntime(s)": f"{wall_time:.6f}",
                            "CompileTime(s)": f"{compile_time:.6f}",
                            "IR_alloca": ir_metrics["IR_alloca"],
                            "IR_load": ir_metrics["IR_load"],
                            "IR_store": ir_metrics["IR_store"],
                            "IR_gep": ir_metrics["IR_gep"],
                            "IR_phi": ir_metrics["IR_phi"],
                            "IR_bb": ir_metrics["IR_bb"],
                            "LLVM_IR_Path": ll_path,
                            "RunRepeats": run_repeats,
                            "TargetSeconds": f"{args.target_seconds:.6f}",
                            "Status": "Success",
                        }
                    )
                    outcsv.flush()

    rows = []
    with open(results_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    summary = aggregate_summary(rows)
    with open(summary_csv, "w", encoding="utf-8", newline="") as f:
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
                "alloca_mean",
                "alloca_med",
                "load_mean",
                "load_med",
                "store_mean",
                "store_med",
                "gep_mean",
                "gep_med",
                "phi_mean",
                "phi_med",
                "bb_mean",
                "bb_med",
            ],
        )
        writer.writeheader()
        for row in summary:
            writer.writerow(row)

    volatility = build_volatility_summary(summary)
    with open(volatility_csv, "w", encoding="utf-8", newline="") as f:
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
        for row in volatility:
            writer.writerow(row)

    interaction_rows = []
    interaction_rows += compute_interaction(summary, "runtime_med", smaller_is_better=True)
    for metric_key in ("alloca_med", "load_med", "store_med", "gep_med", "phi_med", "bb_med"):
        interaction_rows += compute_interaction(summary, metric_key, smaller_is_better=True)

    if interaction_rows:
        with open(inter_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["Variant", "metric", "delta", "M_on_L_on", "M_on_L_off", "M_off_L_on", "M_off_L_off"],
            )
            writer.writeheader()
            for row in interaction_rows:
                writer.writerow(row)

    print(out_dir)


if __name__ == "__main__":
    main()
