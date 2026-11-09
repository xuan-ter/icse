#!/usr/bin/env python3
"""Recompute MIR-LLVM DiD results from frozen raw runs and the generated matrix.

The analysis intentionally identifies cells from configuration IDs and the
generated experiment matrix. Pass labels are used only as a consistency check;
the literal label "All" is never interpreted as the optimized baseline.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parent
INPUTS = ROOT / "inputs"
OUT = ROOT / "results"
BOOTSTRAP_SAMPLES = 50_000
BOOTSTRAP_SEED = 42
ALPHA = 0.05

REAL_BENCHMARKS = [
    "image", "fast_image_resize", "ripgrep", "bat", "eza", "serde",
    "aho-corasick", "regex", "tokio", "hyper", "rustls", "quinn",
]
MICRO_FILES = {
    "loop_hoisting_bench": "loop_hoisting_bench.csv",
    "branch_cfg_bench": "branch_cfg_bench.csv",
    "trait_monomorphization": "trait_monomorphization.csv",
    "iterator_pipeline_bench": "iterator_pipeline_bench.csv",
    "async_state_machine_bench": "async_state_machine_bench.csv",
    "aggregate_scalarization_bench": "aggregate_scalarization_bench.csv",
}
REAL_FILES = {name: f"{name}.csv" for name in REAL_BENCHMARKS}
ALL_FILES = {**REAL_FILES, **MICRO_FILES}
RUNID_BUILD_CLUSTER_BENCHMARKS = {"async_state_machine_bench", "aggregate_scalarization_bench"}


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is None:
        columns = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: scalar(v) for k, v in row.items()})


def scalar(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_label(value: Any) -> str:
    if value is None:
        return "None"
    label = str(value).strip()
    if label.lower() in {"", "none", "nan", "n/a", "na"}:
        return "None"
    return label


def matrix_side(entry: dict[str, Any], side: str) -> dict[str, Any]:
    value = entry.get(side)
    if not isinstance(value, dict):
        return {"pass": "None", "switches": []}
    return {"pass": str(value.get("pass", "None")), "switches": list(value.get("switches") or [])}


def classify_matrix(matrix: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    """Build exact config-id -> cell mapping from generated matrix entries."""
    entries = matrix["combinations"]
    config_map: dict[str, dict[str, Any]] = {}
    mir_passes: set[str] = set()
    llvm_flags: set[str] = set()
    cell_keys: dict[tuple[str, str, str], str] = {}

    for entry in entries:
        name = str(entry.get("name") or entry.get("Experiment_ID") or "").strip()
        if not name:
            raise ValueError("Matrix entry has no configuration name")
        mir = matrix_side(entry, "mir")
        llvm = matrix_side(entry, "llvm")
        ms, ls = mir["switches"], llvm["switches"]
        cell = "excluded_global_or_nonfactorial"
        key: tuple[str, str, str] | None = None

        # The optimized background is the explicitly named baseline entry.
        if name == "EXP_DBL_000_BASELINE" and not ms and not ls:
            cell, key = "00", ("00", "baseline", "baseline")
        elif len(ms) == 1 and ms[0].startswith("-") and not ls:
            cell = "10"
            mir_passes.add(mir["pass"])
            key = (cell, mir["pass"], "baseline")
        elif not ms and len(ls) == 1 and ls[0].startswith("-"):
            cell = "01"
            llvm_flags.add(llvm["pass"])
            key = (cell, "baseline", llvm["pass"])
        elif len(ms) == 1 and ms[0].startswith("-") and len(ls) == 1 and ls[0].startswith("-"):
            cell = "11"
            mir_passes.add(mir["pass"])
            llvm_flags.add(llvm["pass"])
            key = (cell, mir["pass"], llvm["pass"])

        flags = ["-C opt-level=3"]
        if ms:
            flags.append("-Z mir-enable-passes=" + ",".join(ms))
        for switch in ls:
            flags.extend(["-C llvm-args=" + switch])
        config_map[name] = {
            "config_id": name,
            "description": entry.get("description", ""),
            "cell": cell,
            "mir_pass": mir["pass"],
            "llvm_flag": llvm["pass"],
            "mir_switches": ",".join(ms),
            "llvm_switches": ",".join(ls),
            "expected_rustflags": " ".join(flags),
            "matrix_key": key,
        }
        if key is not None:
            if key in cell_keys:
                raise ValueError(f"Duplicate generated cell key {key}: {cell_keys[key]} / {name}")
            cell_keys[key] = name

    if len(mir_passes) != 20 or len(llvm_flags) != 83:
        raise ValueError(f"Expected 20 MIR factors and 83 LLVM controls; got {len(mir_passes)} and {len(llvm_flags)}")
    if len([x for x in config_map.values() if x["cell"] == "11"]) != 20 * 83:
        raise ValueError("Generated matrix does not contain all 1,660 joint-ablation cells")
    if len([x for x in config_map.values() if x["cell"] == "10"]) != 20:
        raise ValueError("Generated matrix does not contain 20 MIR-only cells")
    if len([x for x in config_map.values() if x["cell"] == "01"]) != 83:
        raise ValueError("Generated matrix does not contain 83 LLVM-only cells")
    if len([x for x in config_map.values() if x["cell"] == "00"]) != 1:
        raise ValueError("Generated matrix must identify exactly one optimized baseline")

    config_map["__cell_keys__"] = {"keys": cell_keys}  # type: ignore[assignment]
    return config_map, sorted(mir_passes), sorted(llvm_flags)


def variant_name(row: dict[str, str]) -> str:
    # Trait microbenchmark contains both Group (dataset label) and Case (variant).
    for field in ("Case", "Variant", "Mode"):
        value = row.get(field)
        if value is not None and str(value).strip():
            return str(value).strip()
    return "default"


def numeric(row: dict[str, str], key: str) -> float | None:
    try:
        value = float(row.get(key, ""))
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def bh_adjust(p_values: list[float]) -> list[float]:
    n = len(p_values)
    order = sorted(range(n), key=lambda i: p_values[i])
    adjusted = [1.0] * n
    running = 1.0
    for rank_index in range(n - 1, -1, -1):
        index = order[rank_index]
        rank = rank_index + 1
        running = min(running, p_values[index] * n / rank)
        adjusted[index] = min(1.0, running)
    return adjusted


def bootstrap_weights(n: int, role: int, variant_index: int, benchmark_index: int) -> np.ndarray:
    # Independent weight matrices by cell role preserve independent cell
    # resampling within each DiD contrast. Reusing a role matrix across tests
    # changes only dependence between test statistics, not each marginal test.
    seed = BOOTSTRAP_SEED + benchmark_index * 1_000_003 + variant_index * 10_007 + role * 101 + n
    rng = np.random.default_rng(seed)
    return rng.multinomial(n, np.full(n, 1.0 / n), size=BOOTSTRAP_SAMPLES)


def boot_means(log_values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    return weights @ log_values / len(log_values)


def paired_boot_means(
    run_logs_by_variant: dict[str, dict[str, float]],
    role: int,
    benchmark_index: int,
) -> dict[str, np.ndarray]:
    """Bootstrap shared per-RunID builds jointly across the variants using them."""
    run_ids = sorted({run_id for logs in run_logs_by_variant.values() for run_id in logs})
    if not run_ids:
        return {variant: np.full(BOOTSTRAP_SAMPLES, np.nan) for variant in run_logs_by_variant}
    n = len(run_ids)
    weights = bootstrap_weights(n, role, 0, benchmark_index)
    id_positions = {run_id: i for i, run_id in enumerate(run_ids)}
    positions_by_variant = {
        variant: np.asarray([id_positions[run_id] for run_id in logs], dtype=int)
        for variant, logs in run_logs_by_variant.items()
    }
    # Re-draw the rare bootstrap replicates that contain no observed cluster for
    # a variant with an incomplete RunID set.
    invalid = np.zeros(BOOTSTRAP_SAMPLES, dtype=bool)
    for positions in positions_by_variant.values():
        if len(positions):
            invalid |= weights[:, positions].sum(axis=1) == 0
    if np.any(invalid):
        seed = BOOTSTRAP_SEED + benchmark_index * 1_000_003 + role * 101 + n + 17
        rng = np.random.default_rng(seed)
        while np.any(invalid):
            weights[invalid] = rng.multinomial(n, np.full(n, 1.0 / n), size=int(invalid.sum()))
            invalid[:] = False
            for positions in positions_by_variant.values():
                if len(positions):
                    invalid |= weights[:, positions].sum(axis=1) == 0

    output = {}
    for variant, run_logs in run_logs_by_variant.items():
        positions = positions_by_variant[variant]
        if not len(positions):
            output[variant] = np.full(BOOTSTRAP_SAMPLES, np.nan)
            continue
        values = np.asarray([run_logs[run_id] for run_id in run_logs], dtype=float)
        selected_weights = weights[:, positions]
        output[variant] = selected_weights @ values / selected_weights.sum(axis=1)
    return output


def summarize_boot(point: float, samples: np.ndarray) -> dict[str, float]:
    low, high = np.percentile(samples, [2.5, 97.5])
    p_pos = (int(np.count_nonzero(samples >= 0.0)) + 1) / (len(samples) + 1)
    p_neg = (int(np.count_nonzero(samples <= 0.0)) + 1) / (len(samples) + 1)
    p = min(1.0, 2.0 * min(p_pos, p_neg))
    return {"delta": float(point), "ci_low": float(low), "ci_high": float(high), "p_value": float(p)}


def qtile(values: list[float], q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=float), q))


def verify_row_labels(row: dict[str, str], config: dict[str, Any]) -> bool:
    return (
        clean_label(row.get("MIR_Pass")) == clean_label(config["mir_pass"])
        and clean_label(row.get("LLVM_Pass")) == clean_label(config["llvm_flag"])
    )


def load_benchmark(
    name: str,
    path: Path,
    config_map: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, dict[str, list[dict[str, Any]]]]], list[dict[str, Any]], dict[str, Any]]:
    """Return benchmark -> variant -> config -> valid observations."""
    data: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    mapping_audit: dict[tuple[str, str], dict[str, Any]] = {}
    invalid_rows = Counter()
    total_rows = 0
    run_keys: set[tuple[str, str, str]] = set()
    duplicate_run_ids = 0

    for row in read_csv(path):
        total_rows += 1
        config_id = str(row.get("ConfigName", "")).strip()
        variant = variant_name(row)
        config = config_map.get(config_id)
        audit_key = (config_id, variant)
        if audit_key not in mapping_audit:
            mapping_audit[audit_key] = {
                "benchmark": name,
                "config_id": config_id,
                "variant": variant,
                "cell": config["cell"] if config else "unmapped",
                "mir_pass_expected": config["mir_pass"] if config else "",
                "llvm_flag_expected": config["llvm_flag"] if config else "",
                "mir_pass_observed": clean_label(row.get("MIR_Pass")),
                "llvm_flag_observed": clean_label(row.get("LLVM_Pass")),
                "expected_rustflags": config["expected_rustflags"] if config else "",
                "n_rows": 0,
                "n_usable_runtime": 0,
                "n_success": 0,
                "n_noparsedresults": 0,
                "mapping_status": "unmapped" if config is None else "labels_match",
                "source_status_values": set(),
            }
        audit = mapping_audit[audit_key]
        audit["n_rows"] += 1
        status = str(row.get("Status", "")).strip().lower()
        audit["source_status_values"].add(status or "blank")
        if config is None:
            invalid_rows["unmapped_config"] += 1
            continue
        if not verify_row_labels(row, config):
            audit["mapping_status"] = "label_mismatch"
            invalid_rows["label_mismatch"] += 1
            continue
        if status not in {"success", "noparsedresults", ""}:
            invalid_rows[f"status:{status}"] += 1
            continue
        runtime = numeric(row, "TotalRuntime(s)")
        if runtime is None or runtime <= 0:
            invalid_rows["invalid_runtime"] += 1
            continue
        audit["n_usable_runtime"] += 1
        if status == "success":
            audit["n_success"] += 1
        if status == "noparsedresults":
            audit["n_noparsedresults"] += 1
        run_id = str(row.get("RunID", "")).strip()
        run_key = (config_id, variant, run_id)
        if run_id and run_key in run_keys:
            duplicate_run_ids += 1
        run_keys.add(run_key)
        observation = {"runtime": runtime, "run_id": run_id, "status": status, "row": row}
        data[variant][config_id].append(observation)

    audit_rows = []
    for audit in mapping_audit.values():
        config = config_map.get(audit["config_id"], {})
        values = [o["runtime"] for o in data.get(audit["variant"], {}).get(audit["config_id"], [])]
        audit["runtime_median"] = statistics.median(values) if values else ""
        audit["runtime_iqr"] = (qtile(values, 75) - qtile(values, 25)) if values else ""
        audit["source_status_values"] = ";".join(sorted(audit["source_status_values"]))
        audit["actual_options_in_raw_csv"] = "not_recorded"
        audit_rows.append(audit)

    expected_configs = set(config_map) - {"__cell_keys__"}
    for config_id in expected_configs:
        if not any(k[0] == config_id for k in mapping_audit):
            config = config_map[config_id]
            audit_rows.append({
                "benchmark": name,
                "config_id": config_id,
                "variant": "<missing>",
                "cell": config["cell"],
                "mir_pass_expected": config["mir_pass"],
                "llvm_flag_expected": config["llvm_flag"],
                "mir_pass_observed": "",
                "llvm_flag_observed": "",
                "expected_rustflags": config["expected_rustflags"],
                "n_rows": 0,
                "n_usable_runtime": 0,
                "n_success": 0,
                "n_noparsedresults": 0,
                "mapping_status": "missing_config_in_raw_csv",
                "source_status_values": "",
                "runtime_median": "",
                "runtime_iqr": "",
                "actual_options_in_raw_csv": "not_recorded",
            })

    stats = {
        "benchmark": name,
        "source_file": str(path.relative_to(ROOT)),
        "raw_rows": total_rows,
        "variants": sorted(data),
        "configs_observed": len({key[0] for key in mapping_audit}),
        "invalid_rows": dict(invalid_rows),
        "duplicate_run_id_keys": duplicate_run_ids,
        "n_label_mismatch_groups": sum(1 for r in audit_rows if r.get("mapping_status") == "label_mismatch"),
        "n_missing_config_groups": sum(1 for r in audit_rows if r.get("mapping_status") == "missing_config_in_raw_csv"),
    }
    return data, audit_rows, stats


def cell_config_ids(config_map: dict[str, dict[str, Any]], mir_passes: list[str], llvm_flags: list[str]) -> dict[tuple[str, str, str], str]:
    result = {}
    for config_id, config in config_map.items():
        if config_id == "__cell_keys__" or config["matrix_key"] is None:
            continue
        result[config["matrix_key"]] = config_id
    expected = {("00", "baseline", "baseline")}
    expected.update(("10", mir, "baseline") for mir in mir_passes)
    expected.update(("01", "baseline", llvm) for llvm in llvm_flags)
    expected.update(("11", mir, llvm) for mir in mir_passes for llvm in llvm_flags)
    missing = expected - set(result)
    if missing:
        raise ValueError(f"Generated matrix is missing factorial cells: {list(missing)[:5]}")
    return result


def run_analysis() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    matrix_path = INPUTS / "combined_experiment_matrix.json"
    matrix = json.loads(matrix_path.read_text(encoding="utf-8-sig"))
    config_map, mir_passes, llvm_flags = classify_matrix(matrix)
    config_keys = cell_config_ids(config_map, mir_passes, llvm_flags)

    matrix_rows = []
    for config_id, config in config_map.items():
        if config_id == "__cell_keys__":
            continue
        matrix_rows.append({k: v for k, v in config.items() if k != "matrix_key"})
    write_csv(OUT / "generated_config_mapping.csv", matrix_rows)
    measurement_mapping_stats = write_measurement_cell_mapping(config_map)

    all_interactions: list[dict[str, Any]] = []
    all_variant_interactions: list[dict[str, Any]] = []
    all_mapping_rows: list[dict[str, Any]] = []
    all_stats = []
    summary_by_benchmark: dict[str, Any] = {}

    benchmark_names = list(REAL_BENCHMARKS) + list(MICRO_FILES)
    for benchmark_index, benchmark in enumerate(benchmark_names):
        raw_file = INPUTS / ALL_FILES[benchmark]
        if not raw_file.exists():
            raise FileNotFoundError(raw_file)
        data, mapping_rows, stats = load_benchmark(benchmark, raw_file, config_map)
        all_mapping_rows.extend(mapping_rows)
        all_stats.append(stats)
        variants = sorted(data)

        # Global ablation rows are retained in the audit only and never enter
        # the 2x2 DiD analysis, which is anchored to the opt-level=3 baseline.
        analysis_variants: dict[str, dict[str, dict[str, Any]]] = {}
        for variant_index, variant in enumerate(variants):
            cells: dict[str, dict[str, Any]] = {}
            base_id = config_keys[("00", "baseline", "baseline")]
            if base_id not in data[variant]:
                continue
            baseline = data[variant][base_id]
            cells["00"] = {"config_id": base_id, "observations": baseline}
            # Store each single-ablation cell by factor.
            for mir in mir_passes:
                config_id = config_keys[("10", mir, "baseline")]
                if config_id in data[variant]:
                    cells[f"10|{mir}"] = {"config_id": config_id, "observations": data[variant][config_id]}
            for llvm in llvm_flags:
                config_id = config_keys[("01", "baseline", llvm)]
                if config_id in data[variant]:
                    cells[f"01|{llvm}"] = {"config_id": config_id, "observations": data[variant][config_id]}
            for mir in mir_passes:
                for llvm in llvm_flags:
                    config_id = config_keys[("11", mir, llvm)]
                    if config_id in data[variant]:
                        cells[f"11|{mir}|{llvm}"] = {"config_id": config_id, "observations": data[variant][config_id]}
            analysis_variants[variant] = cells

        # Precompute the 00/10/01 bootstrap distributions. Joint cells are
        # processed in batches below, avoiding thousands of small BLAS calls.
        weights: dict[tuple[str, int], np.ndarray] = {}
        boot_cache: dict[tuple[str, str], np.ndarray] = {}
        cell_stats: dict[tuple[str, str], dict[str, Any]] = {}
        cluster_boot_cache: dict[str, dict[str, np.ndarray]] = {}
        variant_indices = {variant: i for i, variant in enumerate(analysis_variants)}
        for variant, cells in analysis_variants.items():
            for key, cell_data in cells.items():
                obs = cell_data["observations"]
                runtimes = np.asarray([o["runtime"] for o in obs], dtype=float)
                logs = np.log(runtimes)
                n = len(logs)
                cell_stats[(variant, key)] = {
                    "n": n,
                    "median": float(np.median(runtimes)),
                    "iqr": float(np.percentile(runtimes, 75) - np.percentile(runtimes, 25)),
                    "mean_log": float(np.mean(logs)),
                    "logs": logs,
                    "run_logs": {
                        str(o["run_id"]): float(math.log(o["runtime"]))
                        for o in obs if str(o.get("run_id", "")).strip()
                    },
                    "config_id": cell_data["config_id"],
                }
                if benchmark in RUNID_BUILD_CLUSTER_BENCHMARKS and len(cell_stats[(variant, key)]["run_logs"]) != n:
                    raise ValueError(
                        f"{benchmark}/{variant}/{cell_data['config_id']}: RunID must uniquely identify each usable runtime row"
                    )

        # Build cell bootstrap distributions only after all variant/cell data
        # are available, so shared RunID clusters include every observed case.
        for variant, cells in analysis_variants.items():
            variant_index = variant_indices[variant]
            for key, cell_data in cells.items():
                if key.startswith("11|"):
                    continue
                if key.startswith("10|"):
                    role = "10"
                elif key.startswith("01|"):
                    role = "01"
                else:
                    role = "00"
                stats_cell = cell_stats[(variant, key)]
                n = stats_cell["n"]
                if role != "11":
                    if benchmark in RUNID_BUILD_CLUSTER_BENCHMARKS:
                        config_id = cell_data["config_id"]
                        if config_id not in cluster_boot_cache:
                            logs_by_variant = {
                                other_variant: cell_stats[(other_variant, key)]["run_logs"]
                                for other_variant, other_cells in analysis_variants.items()
                                if key in other_cells and (other_variant, key) in cell_stats
                            }
                            # A RunID denotes one build shared by the variants in these
                            # runners. Resample the build IDs jointly and retain the
                            # observed missing-variant pattern within each build.
                            cluster_boot_cache[config_id] = paired_boot_means(
                                logs_by_variant,
                                {"00": 0, "10": 1, "01": 2}[role],
                                benchmark_index,
                            )
                        for other_variant, samples in cluster_boot_cache[config_id].items():
                            boot_cache[(other_variant, key)] = samples
                    else:
                        weight_key = (f"{variant_index}:{role}", n)
                        if weight_key not in weights:
                            weights[weight_key] = bootstrap_weights(n, {"00": 0, "10": 1, "01": 2}[role], variant_index, benchmark_index)
                        boot_cache[(variant, key)] = boot_means(stats_cell["logs"], weights[weight_key])

        pair_defs = [(mir, llvm) for mir in mir_passes for llvm in llvm_flags]
        benchmark_variant_rows: list[dict[str, Any]] = []
        aggregate_rows: list[dict[str, Any]] = []
        batch_size = 64
        for batch_start in range(0, len(pair_defs), batch_size):
            batch = pair_defs[batch_start:batch_start + batch_size]
            aggregate_boot = np.zeros((BOOTSTRAP_SAMPLES, len(batch)), dtype=float)
            aggregate_point = np.zeros(len(batch), dtype=float)
            aggregate_weighted_boot = np.zeros((BOOTSTRAP_SAMPLES, len(batch)), dtype=float)
            aggregate_weighted_point = np.zeros(len(batch), dtype=float)
            aggregate_weight_sums = np.zeros(len(batch), dtype=float)
            variant_rows_by_position: list[list[dict[str, Any]]] = [[] for _ in batch]
            complete_for_all_variants = np.ones(len(batch), dtype=bool)

            if benchmark in RUNID_BUILD_CLUSTER_BENCHMARKS:
                joint_cluster_boot_cache: dict[str, dict[str, np.ndarray]] = {}
                for mir, llvm in batch:
                    joint_key = f"11|{mir}|{llvm}"
                    config_id = config_keys[("11", mir, llvm)]
                    logs_by_variant = {
                        variant: cell_stats[(variant, joint_key)]["run_logs"]
                        for variant, cells in analysis_variants.items()
                        if joint_key in cells and (variant, joint_key) in cell_stats
                    }
                    joint_cluster_boot_cache[config_id] = paired_boot_means(logs_by_variant, 3, benchmark_index)
            else:
                joint_cluster_boot_cache = {}

            for variant, cells in analysis_variants.items():
                variant_index = variant_indices[variant]
                by_joint_n: dict[int, list[tuple[int, str, str, list[dict[str, Any]]]]] = defaultdict(list)
                for local_index, (mir, llvm) in enumerate(batch):
                    keys = ["00", f"10|{mir}", f"01|{llvm}", f"11|{mir}|{llvm}"]
                    if any(key not in cells for key in keys):
                        complete_for_all_variants[local_index] = False
                        continue
                    stats_cells = [cell_stats[(variant, key)] for key in keys]
                    if any(item["n"] <= 0 for item in stats_cells):
                        complete_for_all_variants[local_index] = False
                        continue
                    by_joint_n[stats_cells[3]["n"]].append((local_index, mir, llvm, stats_cells))

                for n11, grouped_pairs in by_joint_n.items():
                    if benchmark in RUNID_BUILD_CLUSTER_BENCHMARKS:
                        boot11 = np.column_stack([
                            joint_cluster_boot_cache[item[3][3]["config_id"]][variant]
                            for item in grouped_pairs
                        ])
                    else:
                        weight_key = (f"{variant_index}:11", n11)
                        if weight_key not in weights:
                            weights[weight_key] = bootstrap_weights(n11, 3, variant_index, benchmark_index)
                        joint_logs = np.column_stack([item[3][3]["logs"] for item in grouped_pairs])
                        boot11 = weights[weight_key] @ joint_logs / n11
                    for col, (local_index, mir, llvm, stats_cells) in enumerate(grouped_pairs):
                        boot00 = boot_cache[(variant, "00")]
                        boot10 = boot_cache[(variant, f"10|{mir}")]
                        boot01 = boot_cache[(variant, f"01|{llvm}")]
                        point = stats_cells[1]["mean_log"] + stats_cells[2]["mean_log"] - stats_cells[0]["mean_log"] - stats_cells[3]["mean_log"]
                        delta_boot = boot10 + boot01 - boot00 - boot11[:, col]
                        aggregate_point[local_index] += point / len(analysis_variants)
                        aggregate_boot[:, local_index] += delta_boot / len(analysis_variants)
                        variant_weight = float(min(item["n"] for item in stats_cells))
                        aggregate_weighted_point[local_index] += point * variant_weight
                        aggregate_weighted_boot[:, local_index] += delta_boot * variant_weight
                        aggregate_weight_sums[local_index] += variant_weight
                        variant_boot_summary = summarize_boot(point, delta_boot)
                        variant_rows_by_position[local_index].append({
                            "benchmark": benchmark,
                            "subject_type": "real_world" if benchmark in REAL_BENCHMARKS else "microbenchmark",
                            "variant": variant,
                            "mir_pass": mir,
                            "llvm_flag": llvm,
                            "delta": point,
                            "ci_low": variant_boot_summary["ci_low"],
                            "ci_high": variant_boot_summary["ci_high"],
                            "p_value": variant_boot_summary["p_value"],
                            "n00": stats_cells[0]["n"], "n10": stats_cells[1]["n"],
                            "n01": stats_cells[2]["n"], "n11": stats_cells[3]["n"],
                            "median00": stats_cells[0]["median"], "median10": stats_cells[1]["median"],
                            "median01": stats_cells[2]["median"], "median11": stats_cells[3]["median"],
                            "iqr00": stats_cells[0]["iqr"], "iqr10": stats_cells[1]["iqr"],
                            "iqr01": stats_cells[2]["iqr"], "iqr11": stats_cells[3]["iqr"],
                            "config00": stats_cells[0]["config_id"], "config10": stats_cells[1]["config_id"],
                            "config01": stats_cells[2]["config_id"], "config11": stats_cells[3]["config_id"],
                        })

            for local_index, (mir, llvm) in enumerate(batch):
                rows_for_pair = variant_rows_by_position[local_index]
                benchmark_variant_rows.extend(rows_for_pair)
                if not complete_for_all_variants[local_index] or len(rows_for_pair) != len(variants):
                    continue
                boot_summary = summarize_boot(float(aggregate_point[local_index]), aggregate_boot[:, local_index])
                aggregate_rows.append({
                    "benchmark": benchmark,
                    "subject_type": "real_world" if benchmark in REAL_BENCHMARKS else "microbenchmark",
                    "mir_pass": mir,
                    "llvm_flag": llvm,
                    "llvm_switch": next(c["llvm_switches"] for c in config_map.values() if c.get("llvm_flag") == llvm and c.get("cell") == "01"),
                    "mir_switch": next(c["mir_switches"] for c in config_map.values() if c.get("mir_pass") == mir and c.get("cell") == "10"),
                    "delta": float(aggregate_point[local_index]),
                    "abs_delta": abs(float(aggregate_point[local_index])),
                    "interaction_ratio": float(math.exp(aggregate_point[local_index])),
                    "interaction_pct": float((math.exp(aggregate_point[local_index]) - 1.0) * 100.0),
                    "ci_low": boot_summary["ci_low"],
                    "ci_high": boot_summary["ci_high"],
                    "p_value": boot_summary["p_value"],
                    "n_variants": len(rows_for_pair),
                    "variants_used": ";".join(row["variant"] for row in rows_for_pair),
                    "n00_total": sum(row["n00"] for row in rows_for_pair),
                    "n10_total": sum(row["n10"] for row in rows_for_pair),
                    "n01_total": sum(row["n01"] for row in rows_for_pair),
                    "n11_total": sum(row["n11"] for row in rows_for_pair),
                    "variant_rule": "equal-weight mean of variant-level DiD; bootstrap within variant then average",
                    "delta_nweighted": float(aggregate_weighted_point[local_index] / aggregate_weight_sums[local_index]),
                    "ci_low_nweighted": float(np.percentile(aggregate_weighted_boot[:, local_index] / aggregate_weight_sums[local_index], 2.5)),
                    "ci_high_nweighted": float(np.percentile(aggregate_weighted_boot[:, local_index] / aggregate_weight_sums[local_index], 97.5)),
                    "p_value_nweighted": summarize_boot(
                        float(aggregate_weighted_point[local_index] / aggregate_weight_sums[local_index]),
                        aggregate_weighted_boot[:, local_index] / aggregate_weight_sums[local_index],
                    )["p_value"],
                    "variant_weight_rule": "sensitivity only: variant weight is min usable n across its four cells",
                })

        if len(aggregate_rows) != 1660:
            raise ValueError(f"{benchmark}: expected 1,660 complete pairs, got {len(aggregate_rows)}")
        q_values = bh_adjust([row["p_value"] for row in aggregate_rows])
        for row, q in zip(aggregate_rows, q_values):
            row["q_value_bh_within_benchmark"] = q
            row["ci_excludes_zero"] = row["ci_low"] > 0.0 or row["ci_high"] < 0.0
            row["highlighted"] = bool(q < ALPHA and row["ci_excludes_zero"])
            row["abs_delta_rank"] = 1 + sum(1 for other in aggregate_rows if other["abs_delta"] > row["abs_delta"])

        all_variant_interactions.extend(benchmark_variant_rows)
        all_interactions.extend(aggregate_rows)
        highlighted = sum(1 for row in aggregate_rows if row["highlighted"])
        summary_by_benchmark[benchmark] = {
            "subject_type": "real_world" if benchmark in REAL_BENCHMARKS else "microbenchmark",
            "input_rows": stats["raw_rows"],
            "variants": variants,
            "complete_pair_results": len(aggregate_rows),
            "highlighted_pairs": highlighted,
            "positive_pairs": sum(1 for row in aggregate_rows if row["delta"] > 0),
            "negative_pairs": sum(1 for row in aggregate_rows if row["delta"] < 0),
            "max_abs_delta": max(row["abs_delta"] for row in aggregate_rows),
            "max_abs_delta_pair": next(row for row in aggregate_rows if row["abs_delta"] == max(x["abs_delta"] for x in aggregate_rows)),
            "n_noparsedresults": sum(int(r["n_noparsedresults"]) for r in mapping_rows),
            "n_mapping_mismatches": stats["n_label_mismatch_groups"],
            "n_missing_configs": stats["n_missing_config_groups"],
        }
        print(f"{benchmark}: {len(aggregate_rows)} pairs, {highlighted} highlighted, max |delta|={summary_by_benchmark[benchmark]['max_abs_delta']:.6f}")

    # The pairwise BH family is 1,660 tests within each benchmark, matching the
    # paper's statistical-analysis description.
    write_csv(OUT / "interaction_results.csv", all_interactions)
    write_csv(OUT / "variant_interaction_results.csv", all_variant_interactions)
    write_csv(OUT / "cell_mapping.csv", all_mapping_rows)

    selected = select_cases(all_interactions)
    write_csv(OUT / "case_selection.csv", selected)
    case_cells = make_case_cell_rows(selected, all_variant_interactions)
    write_csv(OUT / "case_cell_medians.csv", case_cells)
    build_metrics = make_case_build_metrics(case_cells)
    write_csv(OUT / "case_build_metrics.csv", build_metrics)
    structure = make_structure_summary(selected, all_variant_interactions)
    write_csv(OUT / "case_compiler_structure_summary.csv", structure)
    write_csv(OUT / "baseline_audit.csv", make_baseline_audit(all_mapping_rows))
    write_csv(OUT / "input_manifest.csv", make_manifest())

    runlog_audit = audit_run_logs(selected)
    write_csv(OUT / "case_runlog_audit.csv", runlog_audit)
    artifact_audit = make_artifact_audit(selected, case_cells)
    write_csv(OUT / "case_artifact_paths.csv", artifact_audit)
    evidence_ledger = make_evidence_ledger(selected, runlog_audit, artifact_audit, structure)
    write_csv(OUT / "case_evidence_ledger.csv", evidence_ledger)
    build_matrix = make_targeted_build_matrix(selected, case_cells, config_map)
    write_csv(ROOT / "evidence" / "targeted_build_matrix.csv", build_matrix)
    bootstrap_audit = make_bootstrap_unit_audit(benchmark_names)
    write_csv(OUT / "bootstrap_unit_audit.csv", bootstrap_audit)
    trait_sensitivity = [
        {
            "benchmark": row["benchmark"],
            "mir_pass": row["mir_pass"],
            "llvm_flag": row["llvm_flag"],
            "delta_equal_weight": row["delta"],
            "ci_low_equal_weight": row["ci_low"],
            "ci_high_equal_weight": row["ci_high"],
            "p_equal_weight": row["p_value"],
            "delta_min_n_weighted": row["delta_nweighted"],
            "ci_low_min_n_weighted": row["ci_low_nweighted"],
            "ci_high_min_n_weighted": row["ci_high_nweighted"],
            "p_min_n_weighted": row["p_value_nweighted"],
            "q_equal_weight_within_benchmark": row["q_value_bh_within_benchmark"],
            "weight_rule": row["variant_weight_rule"],
        }
        for row in all_interactions if row["benchmark"] == "trait_monomorphization"
    ]
    trait_weighted_q = bh_adjust([row["p_min_n_weighted"] for row in trait_sensitivity])
    for row, q_value in zip(trait_sensitivity, trait_weighted_q):
        row["q_min_n_weighted_within_benchmark"] = q_value
    write_csv(OUT / "trait_variant_weighted_sensitivity.csv", trait_sensitivity)
    report = make_report(selected, case_cells, build_metrics, summary_by_benchmark, all_stats, runlog_audit, artifact_audit)
    (OUT / "case_studies.md").write_text(report, encoding="utf-8")
    paper_draft = make_paper_ready_draft(selected, case_cells, all_variant_interactions, structure, runlog_audit)
    (OUT / "paper_ready_draft.md").write_text(paper_draft, encoding="utf-8")

    summary = {
        "method": {
            "baseline_config_id": "EXP_DBL_000_BASELINE",
            "excluded_global_configs": ["EXP_000_ALL_OFF", "EXP_001_DISABLE_ALL"],
            "delta": "mean(log y10) + mean(log y01) - mean(log y00) - mean(log y11)",
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bh_family": "1,660 pairwise tests within each benchmark",
            "highlight_rule": "BH q < .05 and percentile 95% bootstrap CI excludes zero",
            "multi_variant_rule": "within-variant DiD and bootstrap, then equal-weight average across all variants; incomplete variants exclude that pair",
            "runid_cluster_bootstrap": "async_state_machine_bench and aggregate_scalarization_bench resample RunID build clusters jointly across variants within each configuration, preserving missing outcomes; other benchmark variants are resampled within variant and cell according to the runner's measurement unit",
            "trait_sensitivity_weighting": "variant-weighted sensitivity uses the minimum usable sample count across each variant's four cells; primary trait result remains equal-weighted",
            "bootstrap_unit_audit": "bootstrap_unit_audit.csv",
        },
        "benchmark_count": len(benchmark_names),
        "pairwise_result_count": len(all_interactions),
        "expected_pairwise_result_count": 18 * 1660,
        "complete": len(all_interactions) == 18 * 1660,
        "benchmarks": summary_by_benchmark,
        "input_audit": all_stats,
        "measurement_mapping_audit": measurement_mapping_stats,
        "selected_cases": selected,
        "analysis_code_sha256": sha256(Path(__file__).resolve()),
    }
    (OUT / "analysis_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=scalar), encoding="utf-8")
    return summary


def select_cases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # A case is one complete MIR-pass x LLVM-control comparison. Select one
    # maximum-|Delta| pair within every evaluation subject. Significance is
    # reported, not used to replace a subject's actual maximum with a smaller
    # significant pair.
    selection = []
    benchmarks = sorted({str(row["benchmark"]) for row in rows})
    for benchmark in benchmarks:
        candidates = [row for row in rows if str(row["benchmark"]) == benchmark]
        candidates.sort(key=lambda row: (
            -float(row["abs_delta"]),
            str(row["mir_pass"]),
            str(row["llvm_flag"]),
        ))
        row = candidates[0]
        selection.append({
            "case_role": f"{benchmark}_top_abs_delta",
            "selection_rule": (
                "largest absolute DiD among this evaluation subject's complete pairwise results; "
                "significance is reported but not used to replace the within-subject maximum; "
                "ties broken lexicographically by MIR pass and LLVM control"
            ),
            "within_benchmark_abs_delta_rank": 1,
            "selected_as_exploratory": not bool(row["highlighted"]),
            **row,
        })
    return selection


def make_case_cell_rows(selected: list[dict[str, Any]], variant_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for case in selected:
        for row in variant_rows:
            if row["benchmark"] != case["benchmark"] or row["mir_pass"] != case["mir_pass"] or row["llvm_flag"] != case["llvm_flag"]:
                continue
            for cell in ("00", "10", "01", "11"):
                output.append({
                    "case_role": case["case_role"],
                    "benchmark": case["benchmark"],
                    "variant": row["variant"],
                    "mir_pass": row["mir_pass"],
                    "llvm_flag": row["llvm_flag"],
                    "cell": cell,
                    "config_id": row[f"config{cell}"],
                    "n": row[f"n{cell}"],
                    "runtime_median_s": row[f"median{cell}"],
                    "runtime_iqr_s": row[f"iqr{cell}"],
                    "variant_delta": row["delta"],
                    "variant_ci_low": row["ci_low"],
                    "variant_ci_high": row["ci_high"],
                })
    return output


def summarize_repeated_metric(rows: list[dict[str, str]], tokens: tuple[str, ...]) -> dict[str, Any]:
    """Summarize a config-level metric repeated on runtime rows without treating copies as samples."""
    field = next((key for key in (rows[0].keys() if rows else [])
                  if all(token in key.lower() for token in tokens)), "")
    values = [numeric(row, field) for row in rows] if field else []
    observed = sorted({value for value in values if value is not None})
    return {
        "field": field,
        "record_count": len([value for value in values if value is not None]),
        "unique_value_count": len(observed),
        "value_if_unique": observed[0] if len(observed) == 1 else "",
        "minimum": observed[0] if observed else "",
        "maximum": observed[-1] if observed else "",
    }


def make_case_build_metrics(case_cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract build metrics at the build unit, deduplicating copies on runtime rows."""
    raw_by_benchmark = {
        benchmark: read_csv(INPUTS / filename)
        for benchmark, filename in ALL_FILES.items()
        if any(cell["benchmark"] == benchmark for cell in case_cells)
    }
    output = []
    config_cells: dict[tuple[str, str, str], dict[str, Any]] = {}
    for cell in case_cells:
        key = (cell["case_role"], cell["benchmark"], cell["config_id"])
        config_cells.setdefault(key, dict(cell, variants=set()))["variants"].add(cell["variant"])

    for cell in config_cells.values():
        matching = [
            row for row in raw_by_benchmark[cell["benchmark"]]
            if str(row.get("ConfigName", "")).strip() == cell["config_id"]
            and variant_name(row) in cell["variants"]
        ]
        compile_values: list[float] = []
        size_values: list[float] = []
        within_build_conflicts = False
        if cell["benchmark"] == "async_state_machine_bench":
            # The runner rebuilds once per RunID, then measures each B/L/S variant
            # from that build. Collapse the shared metadata across variants first.
            by_run_id: dict[str, list[dict[str, str]]] = defaultdict(list)
            for row in matching:
                by_run_id[str(row.get("RunID", "")).strip()].append(row)
            for build_rows in by_run_id.values():
                ct = summarize_repeated_metric(build_rows, ("compile", "time"))
                size = summarize_repeated_metric(build_rows, ("binary", "size"))
                if ct["unique_value_count"] == 1:
                    compile_values.append(float(ct["value_if_unique"]))
                elif ct["field"]:
                    within_build_conflicts = True
                if size["unique_value_count"] == 1:
                    size_values.append(float(size["value_if_unique"]))
                elif size["field"]:
                    within_build_conflicts = True
            build_unit_rule = "one rebuild per RunID; deduplicate shared B/L/S variant rows"
        else:
            # The three real-workload runners build once per configuration and
            # copy that one build's metadata to each of ten runtime rows.
            ct = summarize_repeated_metric(matching, ("compile", "time"))
            size = summarize_repeated_metric(matching, ("binary", "size"))
            if ct["unique_value_count"] == 1:
                compile_values.append(float(ct["value_if_unique"]))
            if size["unique_value_count"] == 1:
                size_values.append(float(size["value_if_unique"]))
            within_build_conflicts = ct["unique_value_count"] > 1 or size["unique_value_count"] > 1
            build_unit_rule = "one build per configuration; deduplicate repeated runtime-row metadata"

        build_count = len(compile_values)
        if not matching:
            status = "no_matching_raw_records"
        elif within_build_conflicts:
            status = "conflicting_metadata_within_build_unit"
        elif not compile_values and not size_values:
            status = "build_metrics_not_recorded"
        else:
            status = "build_metadata_deduplicated"
        compile_iqr = qtile(compile_values, 75) - qtile(compile_values, 25) if len(compile_values) > 1 else ""
        unique_sizes = sorted(set(size_values))
        output.append({
            "case_role": cell["case_role"], "benchmark": cell["benchmark"],
            "variants_covered": ";".join(sorted(cell["variants"])),
            "cell": cell["cell"], "config_id": cell["config_id"],
            "build_unit_rule": build_unit_rule,
            "runtime_rows_with_build_metadata": len(matching),
            "build_count": build_count,
            "compile_time_build_count": build_count if compile_values else 0,
            "compile_time_median_s": statistics.median(compile_values) if compile_values else "",
            "compile_time_iqr_s": compile_iqr,
            "compile_time_min_s": min(compile_values) if compile_values else "",
            "compile_time_max_s": max(compile_values) if compile_values else "",
            "binary_size_unique_value_count": len(unique_sizes),
            "binary_size_bytes_if_unique": unique_sizes[0] if len(unique_sizes) == 1 else "",
            "status": status,
            "interpretation": "Build-level recorded metadata; repeated runtime/variant row copies are deduplicated.",
        })
    return output


def make_baseline_audit(mapping_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    meanings = {
        "EXP_DBL_000_BASELINE": "00_optimized_baseline",
        "EXP_000_ALL_OFF": "global_MIR_all_off_excluded",
        "EXP_001_DISABLE_ALL": "global_LLVM_all_off_excluded",
    }
    return [
        {
            "benchmark": row["benchmark"], "variant": row["variant"],
            "config_id": row["config_id"], "interpretation": meanings[row["config_id"]],
            "cell": row["cell"], "n_rows": row["n_rows"],
            "n_usable_runtime": row["n_usable_runtime"],
            "median_runtime_s": row["runtime_median"], "runtime_iqr_s": row["runtime_iqr"],
            "observed_mir_label": row["mir_pass_observed"],
            "observed_llvm_label": row["llvm_flag_observed"],
        }
        for row in mapping_rows if row["config_id"] in meanings
    ]


def make_artifact_audit(selected: list[dict[str, Any]], case_cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for cell in case_cells:
        filename = ALL_FILES[cell["benchmark"]]
        raw_rows = read_csv(INPUTS / filename)
        for raw in raw_rows:
            if str(raw.get("ConfigName", "")).strip() != cell["config_id"] or variant_name(raw) != cell["variant"]:
                continue
            for field, value in raw.items():
                if not value or not ("path" in field.lower() or "_file" in field.lower()):
                    continue
                text = str(value).strip()
                exists = Path(text).exists()
                rows.append({
                    "case_role": cell["case_role"], "benchmark": cell["benchmark"],
                    "variant": cell["variant"], "cell": cell["cell"],
                    "config_id": cell["config_id"], "raw_field": field,
                    "recorded_path": text, "path_exists_at_recorded_location": exists,
                    "interpretation": "available" if exists else "historical path only; artifact unavailable locally",
                })
    for cell in case_cells:
        if not any(r["case_role"] == cell["case_role"] and r["cell"] == cell["cell"] and r["variant"] == cell["variant"] for r in rows):
            rows.append({
                "case_role": cell["case_role"], "benchmark": cell["benchmark"],
                "variant": cell["variant"], "cell": cell["cell"], "config_id": cell["config_id"],
                "raw_field": "", "recorded_path": "", "path_exists_at_recorded_location": False,
                "interpretation": "no artifact path recorded in raw CSV",
            })
    return rows


def make_targeted_build_matrix(
    selected: list[dict[str, Any]],
    case_cells: list[dict[str, Any]],
    config_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    unique_cells: dict[tuple[str, str], dict[str, Any]] = {}
    for cell in case_cells:
        key = (cell["case_role"], cell["config_id"])
        if key not in unique_cells:
            unique_cells[key] = dict(cell, variants=cell["variant"])
        else:
            unique_cells[key]["variants"] += ";" + cell["variant"]
    rows = []
    for cell in unique_cells.values():
        config = config_map[cell["config_id"]]
        rows.append({
            "case_role": cell["case_role"], "benchmark": cell["benchmark"],
            "variants_covered": cell["variants"], "cell": cell["cell"],
            "config_id": cell["config_id"], "mir_pass": cell["mir_pass"],
            "llvm_control": cell["llvm_flag"], "llvm_switch": config["llvm_switches"],
            "mir_switch": config["mir_switches"], "expected_rustflags": config["expected_rustflags"],
            "experiment_toolchain": "rustc 1.98.0-nightly / LLVM 22.1.6 recorded in loop_hoisting log; selected-case match unverified",
            "experiment_source_revision": "not recorded in raw CSV/log; exact commit must be recovered",
            "direct_build_status": "not_run_pending provenance match",
            "requested_artifacts": "MIR dump; LLVM IR; assembly; supported optimization remarks; build log; artifact hashes",
        })
    return rows


def make_structure_summary(selected: list[dict[str, Any]], variant_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarize compiler-structure counters already recorded in raw CSVs."""
    output = []
    prefix_fields = ("IR_", "LLVM_", "MIR_", "LICM_", "HotLoop_", "FactorConst_")
    raw_by_benchmark: dict[str, list[dict[str, str]]] = {}
    for benchmark, filename in ALL_FILES.items():
        raw_by_benchmark[benchmark] = read_csv(INPUTS / filename)

    for case in selected:
        benchmark = case["benchmark"]
        selected_variants = {r["variant"] for r in variant_rows if r["benchmark"] == benchmark and r["mir_pass"] == case["mir_pass"] and r["llvm_flag"] == case["llvm_flag"]}
        target_ids = {r["config_id"] for r in make_case_cell_rows([case], variant_rows)}
        for variant in sorted(selected_variants):
            for cell in ("00", "10", "01", "11"):
                matching = [r for r in raw_by_benchmark[benchmark] if r.get("ConfigName") in target_ids and variant_name(r) == variant]
                matching = [r for r in matching if str(r.get("ConfigName", "")) in {x["config_id"] for x in make_case_cell_rows([case], variant_rows) if x["cell"] == cell}]
                for field in sorted({key for row in matching for key in row if key.startswith(prefix_fields)}):
                    vals = [numeric(row, field) for row in matching]
                    vals = [v for v in vals if v is not None]
                    if vals:
                        output.append({
                            "case_role": case["case_role"], "benchmark": benchmark, "variant": variant,
                            "mir_pass": case["mir_pass"], "llvm_flag": case["llvm_flag"], "cell": cell,
                            "field": field, "n": len(vals), "median": statistics.median(vals),
                            "min": min(vals), "max": max(vals),
                            "interpretation": "recorded structural counter; descriptive association only",
                        })
    return output


def make_manifest() -> list[dict[str, Any]]:
    source_roots = {
        "image.csv": "datas/real_workload/image.csv",
        "fast_image_resize.csv": "datas/real_workload/fast_image_resize.csv",
        "ripgrep.csv": "datas/real_workload/ripgrep.csv",
        "bat.csv": "datas/real_workload/bat.csv",
        "eza.csv": "datas/real_workload/eza.csv",
        "serde.csv": "datas/real_workload/serde.csv",
        "aho-corasick.csv": "datas/real_workload/aho-corasick.csv",
        "regex.csv": "datas/real_workload/regex.csv",
        "tokio.csv": "datas/real_workload/tokio.csv",
        "hyper.csv": "datas/real_workload/hyper.csv",
        "rustls.csv": "datas/real_workload/rustls.csv",
        "quinn.csv": "datas/real_workload/quinn.csv",
        "aggregate_scalarization_bench.csv": "datas/micro_bench/aggregate_scalarization_bench.csv",
        "branch_cfg_bench.csv": "datas/micro_bench/branch_cfg_bench.csv",
        "trait_monomorphization.csv": "datas/micro_bench/trait_monomorphization.csv",
        "iterator_pipeline_bench.csv": "datas/micro_bench/iterator_pipeline_bench.csv",
        "loop_hoisting_bench.csv": "datas/micro_bench/loop_hoisting_bench.csv",
        "async_state_machine_bench.csv": "async_state_machine_bench/results/run_20260602_123232/experiment_results.csv",
        "combined_experiment_matrix.json": "table/table_json/combined_experiment_matrix.json",
        "optimization_factors.csv": "pass_filter/optimization_inventory/optimization_factors.csv",
    }
    rows = []
    for path in sorted(INPUTS.iterdir()):
        if not path.is_file():
            continue
        source_rel = source_roots.get(path.name, "")
        source_path = ROOT.parent / source_rel if source_rel else None
        source_exists = bool(source_path and source_path.exists())
        source_hash = sha256(source_path) if source_exists and source_path else ""
        rows.append({
            "snapshot_file": path.name,
            "original_workspace_source": source_rel,
            "snapshot_bytes": path.stat().st_size,
            "sha256": sha256(path),
            "source_exists": source_exists,
            "source_bytes": source_path.stat().st_size if source_exists and source_path else "",
            "source_sha256": source_hash,
            "snapshot_matches_source": bool(source_exists and source_hash == sha256(path)),
        })
    return rows


def write_measurement_cell_mapping(config_map: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Write one auditable matrix/cell decision for every frozen raw record."""
    output = OUT / "measurement_cell_mapping.csv"
    fields = [
        "measurement_id", "benchmark", "source_file", "source_row_number", "variant",
        "run_id", "config_id", "generated_cell", "generated_mir_pass",
        "generated_mir_switches", "generated_llvm_control", "generated_llvm_switches",
        "expected_rustflags", "observed_mir_label", "observed_llvm_label", "mapping_status",
        "raw_status", "runtime_s", "runtime_usable", "factorial_design_cell",
        "eligible_for_analysis_row", "actual_compile_options_status",
    ]
    audit = Counter()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for benchmark, filename in ALL_FILES.items():
            path = INPUTS / filename
            with path.open(newline="", encoding="utf-8-sig") as source:
                for row_number, row in enumerate(csv.DictReader(source), start=2):
                    config_id = str(row.get("ConfigName", "")).strip()
                    config = config_map.get(config_id)
                    runtime = numeric(row, "TotalRuntime(s)")
                    status = str(row.get("Status", "")).strip().lower()
                    runtime_usable = (
                        status in {"success", "noparsedresults", ""}
                        and runtime is not None and runtime > 0
                    )
                    if config is None:
                        mapping_status = "unmapped_config"
                        cell = "unmapped"
                    else:
                        mapping_status = "labels_match" if verify_row_labels(row, config) else "label_mismatch"
                        cell = config["cell"]
                    writer.writerow({
                        "measurement_id": f"{benchmark}:{row_number}",
                        "benchmark": benchmark,
                        "source_file": filename,
                        "source_row_number": row_number,
                        "variant": variant_name(row),
                        "run_id": row.get("RunID", ""),
                        "config_id": config_id,
                        "generated_cell": cell,
                        "generated_mir_pass": config.get("mir_pass", "") if config else "",
                        "generated_mir_switches": config.get("mir_switches", "") if config else "",
                        "generated_llvm_control": config.get("llvm_flag", "") if config else "",
                        "generated_llvm_switches": config.get("llvm_switches", "") if config else "",
                        "expected_rustflags": config.get("expected_rustflags", "") if config else "",
                        "observed_mir_label": clean_label(row.get("MIR_Pass")),
                        "observed_llvm_label": clean_label(row.get("LLVM_Pass")),
                        "mapping_status": mapping_status,
                        "raw_status": row.get("Status", ""),
                        "runtime_s": runtime if runtime is not None else "",
                        "runtime_usable": runtime_usable,
                        "factorial_design_cell": bool(config and cell in {"00", "10", "01", "11"}),
                        "eligible_for_analysis_row": bool(
                            config and cell in {"00", "10", "01", "11"}
                            and mapping_status == "labels_match" and runtime_usable
                        ),
                        "actual_compile_options_status": "not_recorded_in_raw_csv; selected-case logs audited separately",
                    })
                    audit["rows"] += 1
                    audit[f"mapping_status:{mapping_status}"] += 1
                    audit["runtime_usable_rows"] += int(runtime_usable)
                    audit["factorial_design_rows"] += int(bool(config and cell in {"00", "10", "01", "11"}))
                    audit["eligible_analysis_rows"] += int(bool(
                        config and cell in {"00", "10", "01", "11"}
                        and mapping_status == "labels_match" and runtime_usable
                    ))
    return dict(audit)


def make_bootstrap_unit_audit(benchmarks: list[str]) -> list[dict[str, Any]]:
    """Document the resampling unit inferred from each experiment runner."""
    rows = []
    for benchmark in benchmarks:
        cluster_config_count = ""
        cluster_count_total = ""
        incomplete_cluster_configs = ""
        missing_variant_outcomes = ""
        expected_runid_count = ""
        expected_cluster_count = ""
        missing_entire_build_clusters = ""
        configs_missing_entire_build_clusters = ""
        if benchmark in RUNID_BUILD_CLUSTER_BENCHMARKS:
            unit = "RunID build cluster within configuration"
            method = "joint cluster bootstrap across variants; each selected RunID contributes all observed variant outcomes"
            missing = "the unobserved variant outcome remains missing; bootstrap means normalize over observed clusters, and draws with no cluster for a variant are rejected"
            runner_basis = "runner rebuilds once per RunID, then measures all variants from that build"
            by_config: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
            for raw in read_csv(INPUTS / ALL_FILES[benchmark]):
                runtime = numeric(raw, "TotalRuntime(s)")
                status = str(raw.get("Status", "")).strip().lower()
                if status in {"success", "noparsedresults", ""} and runtime is not None and runtime > 0:
                    by_config[str(raw.get("ConfigName", ""))][variant_name(raw)].add(str(raw.get("RunID", "")))
            runid_universe = set().union(*(
                ids for variants_by_config in by_config.values() for ids in variants_by_config.values()
            )) if by_config else set()
            incomplete = 0
            missing_count = 0
            cluster_total = 0
            missing_entire_count = 0
            configs_missing_entire = 0
            for variants_by_config in by_config.values():
                union = set().union(*variants_by_config.values()) if variants_by_config else set()
                cluster_total += len(union)
                any_missing = any(ids != union for ids in variants_by_config.values())
                incomplete += int(any_missing)
                missing_count += sum(len(union - ids) for ids in variants_by_config.values())
                missing_entire = len(runid_universe - union)
                missing_entire_count += missing_entire
                configs_missing_entire += int(missing_entire > 0)
            cluster_config_count = len(by_config)
            cluster_count_total = cluster_total
            incomplete_cluster_configs = incomplete
            missing_variant_outcomes = missing_count
            expected_runid_count = len(runid_universe)
            expected_cluster_count = cluster_config_count * expected_runid_count
            missing_entire_build_clusters = missing_entire_count
            configs_missing_entire_build_clusters = configs_missing_entire
        elif benchmark == "trait_monomorphization":
            unit = "runtime repeat within variant and configuration"
            method = "resample each variant/cell runtime repeats; the runner builds once per configuration and measures cases in separate repeat loops"
            missing = "a missing repeat is absent from that variant/cell and is not imputed"
            runner_basis = "trait_test/experiment_trait_mir_llvm_hybrid.py: one build per configuration, then separate case-specific runtime loops"
        elif benchmark in {"branch_cfg_bench", "iterator_pipeline_bench"}:
            unit = "runtime repeat within variant and configuration"
            method = "resample each variant/cell runtime repeats; variants are separate runtime executions using one configuration build"
            missing = "a missing repeat is absent from that variant/cell and is not imputed"
            runner_basis = "experiment runner builds each configuration once, then measures each variant over RunID repeats"
        elif benchmark == "loop_hoisting_bench":
            unit = "runtime repeat within mode and configuration"
            method = "resample each mode/cell runtime repeats"
            missing = "a missing repeat is absent from that mode/cell and is not imputed"
            runner_basis = "loop-optimization runner builds and measures each configured mode independently"
        else:
            unit = "runtime RunID within configuration"
            method = "resample successful runtime observations within each cell; this dataset has one analysis variant"
            missing = "failed or invalid runtime rows are excluded and counted in the cell mapping audit"
            runner_basis = "single-variant experiment; RunID identifies a repeated runtime observation"
        rows.append({
            "benchmark": benchmark,
            "bootstrap_unit": unit,
            "bootstrap_method": method,
            "missingness_policy": missing,
            "runner_basis": runner_basis,
            "cluster_config_count": cluster_config_count,
            "runid_cluster_count_total": cluster_count_total,
            "incomplete_cluster_config_count": incomplete_cluster_configs,
            "missing_variant_outcome_count": missing_variant_outcomes,
            "observed_runid_count_per_configuration": expected_runid_count,
            "expected_build_cluster_count": expected_cluster_count,
            "missing_entire_build_cluster_count": missing_entire_build_clusters,
            "configs_missing_entire_build_clusters": configs_missing_entire_build_clusters,
        })
    return rows


def audit_run_logs(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Look for exact selected config names and RUSTFLAGS in known logs."""
    known_logs = {
        "quinn": [ROOT.parent / "quinn/results/20260620_141956/experiment_execution.log"],
        "trait_monomorphization": [ROOT.parent / "trait_test/results/20260615_153358/experiment_execution.log"],
        "ripgrep": [ROOT.parent / "ripgrep/results/run_20260611_172539/experiment_execution.log"],
        "bat": [ROOT.parent / "bat/results/20260605_113508/experiment_execution.log"],
        "loop_hoisting_bench": [ROOT.parent / "loop_hoisting_bench/results/run_20260617_002252/experiment_execution.log"],
        "async_state_machine_bench": [ROOT.parent / "async_state_machine_bench/results/run_20260604_234727/experiment_execution.log"],
        "aggregate_scalarization_bench": [ROOT.parent / "aggregate_scalarization_bench/experiment.log"],
    }
    matrix = json.loads((INPUTS / "combined_experiment_matrix.json").read_text(encoding="utf-8-sig"))
    config_map, _, _ = classify_matrix(matrix)
    rows = []
    for case in selected:
        pair_config_ids = {
            "00": "EXP_DBL_000_BASELINE",
            "10": next((config_id for config_id, config in config_map.items() if config_id != "__cell_keys__" and config["cell"] == "10" and config["mir_pass"] == case["mir_pass"]), ""),
            "01": next((config_id for config_id, config in config_map.items() if config_id != "__cell_keys__" and config["cell"] == "01" and config["llvm_flag"] == case["llvm_flag"]), ""),
            "11": next((config_id for config_id, config in config_map.items() if config_id != "__cell_keys__" and config["cell"] == "11" and config["mir_pass"] == case["mir_pass"] and config["llvm_flag"] == case["llvm_flag"]), ""),
        }
        logs = known_logs.get(case["benchmark"], [])
        for log_path in logs:
            exists = log_path.exists()
            found: dict[str, str] = {}
            if exists:
                wanted = set(pair_config_ids.values())
                current_config = ""
                for line in log_path.open("r", encoding="utf-8", errors="replace"):
                    if line.startswith("[Exp] ") or line.startswith("[Build] "):
                        current_config = line.split("] ", 1)[1].strip().split()[0]
                    elif line.startswith("[Flags] ") and current_config in wanted:
                        found[current_config] = line[len("[Flags] "):].strip()
                        if wanted.issubset(found):
                            break
            exact_flags = {}
            for cell, config_id in pair_config_ids.items():
                expected = config_map.get(config_id, {}).get("expected_rustflags", "")
                observed_tokens = set(found.get(config_id, "").split())
                expected_tokens = set(expected.split())
                exact_flags[cell] = "matrix_flags_verified" if expected_tokens.issubset(observed_tokens) else ("mismatch" if config_id in found else "not_found")
            rows.append({
                "case_role": case["case_role"], "benchmark": case["benchmark"],
                "log_path": str(log_path), "log_exists": exists,
                "config00": pair_config_ids["00"], "config10": pair_config_ids["10"],
                "config01": pair_config_ids["01"], "config11": pair_config_ids["11"],
                "flags00_status": exact_flags["00"], "flags10_status": exact_flags["10"],
                "flags01_status": exact_flags["01"], "flags11_status": exact_flags["11"],
                "flags00_observed": found.get(pair_config_ids["00"], ""),
                "flags10_observed": found.get(pair_config_ids["10"], ""),
                "flags01_observed": found.get(pair_config_ids["01"], ""),
                "flags11_observed": found.get(pair_config_ids["11"], ""),
                "note": "only an exact [Flags] line in the associated experiment log verifies applied options; raw CSV does not store RUSTFLAGS",
            })
        if not logs:
            rows.append({
                "case_role": case["case_role"], "benchmark": case["benchmark"], "log_path": "",
                "log_exists": False, "config00": "EXP_DBL_000_BASELINE",
                "config10": "", "config01": "", "config11": "",
                "flags00_status": "unavailable", "flags10_status": "unavailable",
                "flags01_status": "unavailable", "flags11_status": "unavailable",
                "note": "no known experiment log registered for this workload",
            })
    return rows


def make_evidence_ledger(
    selected: list[dict[str, Any]],
    runlog_audit: list[dict[str, Any]],
    artifact_audit: list[dict[str, Any]],
    structure_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Combine statistical selection and the available compiler provenance."""
    output = []
    for case in selected:
        role = case["case_role"]
        runlog = next((r for r in runlog_audit if r["case_role"] == role), {})
        flags = {cell: runlog.get(f"flags{cell}_status", "unavailable") for cell in ("00", "10", "01", "11")}
        artifacts = [r for r in artifact_audit if r["case_role"] == role]
        unique_artifacts = {
            (r.get("cell", ""), r.get("raw_field", ""), r.get("recorded_path", "")): r
            for r in artifacts if r.get("recorded_path", "")
        }
        local_artifact_cells = sorted({cell for (cell, _, _), r in unique_artifacts.items() if str(r.get("path_exists_at_recorded_location", "")).lower() == "true"})
        structure = [r for r in structure_rows if r["case_role"] == role]
        counters_by_field: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for row in structure:
            counters_by_field[str(row["field"])][str(row["cell"])].add(str(row["median"]))
        changed_counters = []
        for field, by_cell in counters_by_field.items():
            values = {value for cell_values in by_cell.values() for value in cell_values}
            if len(values) > 1:
                changed_counters.append(field)
        output.append({
            "case_role": role,
            "benchmark": case["benchmark"],
            "mir_pass": case["mir_pass"],
            "llvm_control": case["llvm_flag"],
            "llvm_full_flag": case["llvm_switch"],
            "delta": case["delta"],
            "ci_low": case["ci_low"],
            "ci_high": case["ci_high"],
            "q_value_bh": case["q_value_bh_within_benchmark"],
            "flags00_status": flags["00"],
            "flags10_status": flags["10"],
            "flags01_status": flags["01"],
            "flags11_status": flags["11"],
            "verified_flag_cells": sum(value == "matrix_flags_verified" for value in flags.values()),
            "unique_historical_artifact_paths": len(unique_artifacts),
            "locally_available_artifact_cells": ";".join(local_artifact_cells),
            "recorded_structure_fields": ";".join(sorted(counters_by_field)),
            "structure_fields_changing_across_cells": ";".join(sorted(changed_counters)),
            "source_revision_status": "not established by frozen raw CSV or selected-case logs",
            "toolchain_status": "not tied to all four selected measurements",
            "compiler_artifact_status": "no matching local MIR/LLVM IR/assembly/remarks provenance for all four cells" if not local_artifact_cells else "some historical artifacts resolve locally; provenance still requires review",
            "interpretation": "descriptive compiler/runtime evidence; does not establish pass-level or background-independent causality",
        })
    return output


def make_report(
    selected: list[dict[str, Any]],
    case_cells: list[dict[str, Any]],
    build_metrics: list[dict[str, Any]],
    summary: dict[str, Any],
    input_stats: list[dict[str, Any]],
    runlog_audit: list[dict[str, Any]],
    artifact_audit: list[dict[str, Any]],
) -> str:
    selected_workloads = sorted({case["benchmark"] for case in selected})
    highlighted_count = sum(bool(case["highlighted"]) for case in selected)
    lines = [
        "# Per-subject maximum-|Delta| MIR-LLVM case studies",
        "",
        "This report was generated from the frozen CSV snapshots in `../inputs/` by `../analyze_large_delta.py`.",
        "",
        "## Analysis baseline and statistical method",
        "",
        "The 2x2 analysis baseline is the generated-matrix entry `EXP_DBL_000_BASELINE` with empty MIR and LLVM switch lists and `-C opt-level=3`. The global MIR ablation (`EXP_000_ALL_OFF`) and global LLVM ablation (`EXP_001_DISABLE_ALL`) are retained in the audit but excluded from all four factorial cells. The literal `All` is never mapped to the default baseline.",
        "",
        "For each pair, the script computes `Delta = mean(log y10) + mean(log y01) - mean(log y00) - mean(log y11)`. It uses 50,000 percentile-bootstrap replicates. In `async_state_machine_bench` and `aggregate_scalarization_bench`, each RunID is a rebuild shared across variants, so the script resamples RunID build clusters jointly within each configuration and keeps missing variant outcomes missing. Other datasets are resampled at their runner-defined runtime-repeat unit within each cell/variant. Variant-level Δ, 95% CI, and raw p values are written to `variant_interaction_results.csv`; the primary multi-variant estimate is the equal-weight average of variant-level Δ values, and a pair is omitted if a declared variant lacks any of its four cells. Benjamini-Hochberg correction is performed over the 1,660 pairwise tests separately within each benchmark, following Section III.E of the paper. A highlighted result requires q < .05 and a 95% bootstrap interval excluding zero.",
        "",
        "The 95% intervals for selected extremes are ordinary bootstrap intervals and are not adjusted for the fact that cases were selected from the same result set. Treat case-level inferential claims as exploratory; the full corrected result table is the primary statistical output.",
        "",
        "## Selected cases",
        "",
        f"A case is one MIR-pass × LLVM-control pair. We select the largest-|Δ| complete comparison within each of the {len(selected_workloads)} evaluation subjects ({', '.join(selected_workloads)}); each subject contributes one case. These are within-subject maxima, not necessarily large effects in the global ranking. Significance is reported but does not change the within-subject ranking: {highlighted_count}/{len(selected)} selected maxima meet the pre-specified highlight criterion (BH q < .05 and a 95% interval excluding zero).",
        "",
        "| Role | Benchmark | MIR pass | LLVM control flag | Full flag | Delta | exp(Delta) | 95% CI | BH q | Highlighted |",
        "|---|---|---|---|---|---:|---:|---|---:|:---:|",
    ]
    for case in selected:
        lines.append(
            f"| {case['case_role']} | {case['benchmark']} | `{case['mir_pass']}` | `{case['llvm_flag']}` | `{case.get('llvm_switch','')}` | {case['delta']:.4f} | {case['interaction_ratio']:.3f} | [{case['ci_low']:.4f}, {case['ci_high']:.4f}] | {case['q_value_bh_within_benchmark']:.4g} | {'yes' if case['highlighted'] else 'no'} |"
        )
    lines += [
        "",
        "Under the paper's sign convention, positive Delta indicates that the joint ablation is less detrimental than additivity predicts; negative Delta indicates a more detrimental joint effect. exp(Delta) is the multiplicative interaction contrast, not a direct speedup percentage. Read each case's four-cell medians as a configuration-level runtime pattern alongside its log-mean Δ; neither the sign nor the size of Δ by itself identifies a compiler mechanism.",
    ]
    lines += ["", "### Four-cell runtime medians", "", "Medians describe repeated runs; the DiD estimate above is computed from log-runtime means. For multi-variant cases, inspect each variant separately in the table.", ""]
    for case in selected:
        case_rows = [r for r in case_cells if r["case_role"] == case["case_role"]]
        lines += [f"**{case['case_role']} — {case['benchmark']} ({case['mir_pass']} × {case['llvm_flag']})**", "", "| Variant | Cell | Config | n | Median runtime (s) | IQR (s) |", "|---|---|---|---:|---:|---:|"]
        for row in case_rows:
            lines.append(f"| {row['variant']} | {row['cell']} | `{row['config_id']}` | {row['n']} | {row['runtime_median_s']:.6g} | {row['runtime_iqr_s']:.6g} |")
        lines.append("")

    lines += [
        "### Build metadata (supplementary)",
        "",
        "`case_build_metrics.csv` contains compile-time and binary-size values from the experiment result records. Where the runner builds once per configuration and repeats that build metadata across runtime rows, the table records that single build. For `async_state_machine_bench` and `aggregate_scalarization_bench`, the runner rebuilds once per RunID and shares each build across variants; summaries report RunID-level medians and IQRs after deduplicating variant copies.",
        "",
        "| Case | Compile time, 00 / 10 / 01 / 11 (s) | Binary size, 00 / 10 / 01 / 11 (bytes) |",
        "|---|---|---|",
    ]
    cell_order = {"00": 0, "10": 1, "01": 2, "11": 3}
    for case in selected:
        metrics = sorted(
            (row for row in build_metrics if row["case_role"] == case["case_role"]),
            key=lambda row: cell_order[row["cell"]],
        )
        compile_parts = []
        sizes = []
        for row in metrics:
            median_value = row["compile_time_median_s"]
            if median_value == "":
                compile_parts.append("n/a")
            elif row["compile_time_iqr_s"] != "":
                compile_parts.append(f"{median_value:.3f} [{row['compile_time_iqr_s']:.3f}]")
            else:
                compile_parts.append(f"{median_value:.3f}")
            sizes.append(row["binary_size_bytes_if_unique"])
        size_text = f"{int(sizes[0]):,} each" if sizes and all(x == sizes[0] and x != "" for x in sizes) else "see `case_build_metrics.csv`"
        lines.append(f"| {case['benchmark']} | {' / '.join(compile_parts)} | {size_text} |")
    lines += [
        "",
        "RunID-rebuilt microbenchmark entries are median [IQR]; single-build-per-configuration cases have no across-build spread in the original experiment records.",
        "",
    ]

    lines += [
        "## Compiler evidence and limits",
        "",
        "The raw datasets contain a varying set of structural counters (for example IR basic blocks, PHI nodes, loads/stores, or loop-specific MIR/LICM counters). `case_compiler_structure_summary.csv` reports those recorded fields by selected case and cell where available. The source CSVs generally store historical absolute artifact paths, not the MIR dump, LLVM IR, assembly, or remarks themselves; `case_artifact_paths.csv` audits these references, and `case_evidence_ledger.csv` combines their availability with flag and revision provenance by case.",
        "",
        "The raw CSV does not record applied RUSTFLAGS. `measurement_cell_mapping.csv` maps every frozen measurement row to the generated configuration matrix and expected options; `case_runlog_audit.csv` separately checks exact `[Flags]` lines for selected cases when a matching execution log is available. Thus matrix-derived cell identity is auditable, while actual applied-option provenance is only confirmed for rows backed by those logs. `evidence/targeted_build_matrix.csv` lists the four factorial configurations for each selected within-subject maximum. A supplemental full-dependency-graph build was completed for four representative cases (16/16 cells, all smoke runs successful), with MIR dumps, LLVM IR, assembly, optimization remarks, and build records under `evidence/representative_runs/run_20261023_full_graph/`; the report and per-cell remark summaries are in that directory's `analysis/` folder. These artifacts use rustc 1.92.0-nightly/LLVM 21.1.2 and the current source snapshot, whereas historical runtime records identify rustc 1.98.0-nightly/LLVM 22.1.6 and do not provide per-run source revisions. They are supplemental explanatory evidence and cannot be treated as compiler artifacts from the historical timing runs. Recorded IR counters, remarks, and new artifacts are descriptive; they do not establish that a particular pass independently caused the interaction.",
        "",
        "`case_build_metrics.csv` extracts recorded compile-time and binary-size metadata at the build-unit level. Runtime-row copies and variant copies from the same build are deduplicated; async-state-machine summaries use the ten separate RunID rebuilds. No repeated metadata copies are treated as independent builds.",
        "",
        "A compiler control flag may gate a broader decision or multiple passes. Interpret the LLVM factor as the exact command-line control in the matrix, and use the factor inventory to describe its mechanism only at the level supported by that inventory and compiler remarks.",
        "",
        "## Data coverage",
        "",
        "| Benchmark | Type | Raw rows | Variants | Pair results | Highlighted | Mapping mismatches | Missing configs |",
        "|---|---|---:|---|---:|---:|---:|---:|",
    ]
    for item in input_stats:
        b = item["benchmark"]
        s = summary[b]
        lines.append(f"| {b} | {s['subject_type']} | {item['raw_rows']} | {', '.join(item['variants'])} | {s['complete_pair_results']} | {s['highlighted_pairs']} | {item['n_label_mismatch_groups']} | {item['n_missing_config_groups']} |")
    lines += ["", "`fast_image_resize` records six positive wall-clock measurements per configuration, all with `NoParsedResults`. The experiment log shows successful benchmark-process completion, so the recorded wrapper runtime is retained as the primary response; benchmark-specific parsed estimates are unavailable and this metric deserves a sensitivity check. `async_state_machine_bench` uses its full 1,766-configuration run file. In one configuration, observed RunID 7 is absent for variants B and L, and RunIDs 8–10 have no rows for any variant; these outcomes are not imputed. The cluster bootstrap resamples the seven observed build IDs in that configuration and retains the partial B/L missingness.", ""]
    lines += ["`measurement_cell_mapping.csv` contains one row per frozen measurement and records the generated cell, observed labels, expected flags, runtime validity, and whether the row is eligible for factorial analysis. `input_manifest.csv` records SHA-256 for each snapshot and checks whether it still matches the corresponding workspace source. `bootstrap_unit_audit.csv` documents the resampling unit and missing clusters by benchmark; `trait_variant_weighted_sensitivity.csv` reports the trait benchmark's effective-repeat-weighted sensitivity alongside its equal-weight primary estimate.", ""]
    lines += ["## Reproduction", "", "Run from this directory with Python and NumPy available:", "", "```powershell", "python .\\analyze_large_delta.py", "```", "", "The script rewrites generated result files under `results/` and records SHA-256 hashes for the frozen inputs in `results/input_manifest.csv`.", ""]
    return "\n".join(lines)


def make_paper_ready_draft(
    selected: list[dict[str, Any]],
    case_cells: list[dict[str, Any]],
    variant_rows: list[dict[str, Any]],
    structure_rows: list[dict[str, Any]],
    runlog_audit: list[dict[str, Any]],
) -> str:
    """Generate a manuscript-ready draft from the current corrected outputs."""
    lines = [
        "# Draft text for Section IV.D and Section V.C",
        "",
        "## IV.D. Per-Workload Maximum Conditional Interaction Effects",
        "",
        f"To examine conditional interaction effects across the evaluation set, we treated each case as a specific MIR-pass × LLVM-control comparison and selected the largest absolute Δ estimate within each of the {len(selected)} evaluation subjects (12 real-world workloads and six microbenchmarks). These are within-subject maxima, not necessarily large effects in the global ranking. Statistical significance was not used to substitute a smaller pair for a subject's maximum; each selected estimate is labeled with its confidence interval and within-benchmark BH-adjusted p value. For each case, we report the four cell runtime medians, sample counts, and log-runtime DiD estimate. The estimates remain conditional on the fixed optimized background.",
        "",
        "| Case | Benchmark and variant | MIR pass | LLVM control | Cell medians 00 / 10 / 01 / 11 (s; n) | Δ | 95% bootstrap CI | BH q | Recorded compiler evidence |",
        "|---|---|---|---|---|---:|---|---:|---|",
    ]
    cell_order = ("00", "10", "01", "11")
    for case in selected:
        rows = [r for r in case_cells if r["case_role"] == case["case_role"]]
        variants = sorted({r["variant"] for r in rows})
        cell_text = []
        for cell in cell_order:
            cell_rows = sorted((r for r in rows if r["cell"] == cell), key=lambda r: r["variant"])
            if len(variants) == 1:
                if cell_rows:
                    row = cell_rows[0]
                    cell_text.append(f"{row['runtime_median_s']:.4g} (n={row['n']})")
                else:
                    cell_text.append("n/a")
            else:
                cell_text.append("; ".join(f"{r['variant']} {r['runtime_median_s']:.4g} (n={r['n']})" for r in cell_rows))

        factors = [
            r for r in structure_rows
            if r["case_role"] == case["case_role"]
        ]
        variable_fields = []
        all_fields = sorted({r["field"] for r in factors})
        for field in all_fields:
            field_rows = [r for r in factors if r["field"] == field]
            by_cell = {r["cell"]: r["median"] for r in field_rows}
            if len({by_cell.get(cell) for cell in cell_order}) > 1:
                variable_fields.append(field)
        if not factors:
            evidence = "no usable structural counters recorded"
        elif variable_fields:
            evidence = "recorded counter changes: " + ", ".join(variable_fields[:3])
        else:
            evidence = "recorded aggregate MIR/LLVM counters unchanged across cells"

        label = case["case_role"].replace("_", " ")
        variant_label = ", ".join(variants)
        lines.append(
            f"| {label} | {case['benchmark']} ({variant_label}) | `{case['mir_pass']}` | `{case['llvm_switch']}` | "
            f"{' / '.join(cell_text)} | {case['delta']:+.4f} | [{case['ci_low']:+.4f}, {case['ci_high']:+.4f}] | "
            f"{case['q_value_bh_within_benchmark']:.3g} | {evidence} |"
        )

    for case in selected:
        rows = [
            r for r in variant_rows
            if r["benchmark"] == case["benchmark"]
            and r["mir_pass"] == case["mir_pass"]
            and r["llvm_flag"] == case["llvm_flag"]
        ]
        if len(rows) > 1:
            variant_text = "; ".join(
                f"{r['variant']}: Δ={r['delta']:+.4f}, 95% CI [{r['ci_low']:+.4f}, {r['ci_high']:+.4f}], p={r['p_value']:.3g}"
                for r in sorted(rows, key=lambda r: r["variant"])
            )
            lines += ["", f"Variant-level estimates for `{case['benchmark']}` are: {variant_text}."]

    verified_by_role = {}
    for row in runlog_audit:
        statuses = [row.get(f"flags{cell}_status", "") for cell in ("00", "10", "01", "11")]
        verified_by_role[row["case_role"]] = sum(status == "matrix_flags_verified" for status in statuses)
    verification = "; ".join(
        f"{case['benchmark']}: {verified_by_role.get(case['case_role'], 0)}/4 cell flags confirmed in logs"
        for case in selected
    )
    lines += [
        "",
        "Cell medians summarize repeated measurements; Δ is calculated from the four cell means of log runtime. For `async_state_machine_bench` and `aggregate_scalarization_bench`, RunID build clusters are resampled jointly across variants, preserving missing variant outcomes. Trait variants are analyzed separately, with equal weights in the primary estimate; a minimum-cell-sample-size weighted sensitivity analysis is provided in the artifact.",
        "",
        f"Historical compiler evidence is limited to aggregate structural counters in the frozen CSVs and the available execution logs ({verification}); those records do not consistently bind the timing runs to recoverable source revisions and toolchain versions. In a separate supplemental run, the four representative cases were rebuilt across all 16 factorial cells with the current source snapshot and rustc 1.92.0-nightly/LLVM 21.1.2. MIR, LLVM IR, assembly, optimization remarks, commands, build times, and hashes are recorded under `evidence/representative_runs/run_20261023_full_graph/`, with a case report at `evidence/representative_runs/run_20261023_full_graph/analysis/representative_compiler_evidence.md`. Because this toolchain differs from the historical rustc 1.98.0-nightly/LLVM 22.1.6 and historical per-run source revisions are unavailable, these artifacts support candidate explanations but do not reproduce the compiler outputs associated with the reported runtimes. The observed runtime and representation patterns therefore support descriptive interpretation, not a claim that a particular pass independently caused the interaction.",
        "",
        "Each selected case is the maximum-|Δ| comparison within its evaluation subject. The ordinary bootstrap intervals and within-subject BH q values are not additionally adjusted for selecting these maxima, so case-level interpretation is exploratory. All estimates are conditional on the tested optimized background, compiler configuration, hardware, and workload inputs; they do not establish a background-independent or general causal mechanism.",
        "",
        "## V.C. Threats to Validity addition",
        "",
        "The case studies select one maximum-|Δ| comparison within each of the 18 evaluation subjects. The ordinary bootstrap intervals and within-benchmark BH q values are not additionally adjusted for this within-subject extreme-value selection, so case-level results are exploratory and descriptive. Compiler-structure counters and any available or subsequently collected compiler artifacts provide explanatory evidence, but do not by themselves prove a general causal mechanism. Every Δ is conditional on the tested optimized background, toolchain, platform, and workload inputs; conclusions should not be extrapolated to untested benchmarks, compiler versions, or optimization combinations.",
    ]
    return "\n".join(lines) + "\n"


def parse_csv_scalars(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Restore scalar types when refreshing derived case files from saved tables."""
    parsed = []
    for row in rows:
        item: dict[str, Any] = {}
        for key, value in row.items():
            if value == "True":
                item[key] = True
            elif value == "False":
                item[key] = False
            elif value == "" or value is None:
                item[key] = value
            else:
                try:
                    number = float(value)
                    item[key] = int(number) if number.is_integer() else number
                except (TypeError, ValueError):
                    item[key] = value
        parsed.append(item)
    return parsed


def refresh_case_outputs() -> dict[str, Any]:
    """Refresh selection-dependent artifacts without rerunning the bootstrap."""
    interactions = parse_csv_scalars(read_csv(OUT / "interaction_results.csv"))
    variant_interactions = parse_csv_scalars(read_csv(OUT / "variant_interaction_results.csv"))
    if len(interactions) != 18 * 1660:
        raise ValueError(f"Expected 29,880 saved pair results, found {len(interactions)}")

    summary_path = OUT / "analysis_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    selected = select_cases(interactions)
    write_csv(OUT / "case_selection.csv", selected)
    case_cells = make_case_cell_rows(selected, variant_interactions)
    write_csv(OUT / "case_cell_medians.csv", case_cells)
    build_metrics = make_case_build_metrics(case_cells)
    write_csv(OUT / "case_build_metrics.csv", build_metrics)
    structure = make_structure_summary(selected, variant_interactions)
    write_csv(OUT / "case_compiler_structure_summary.csv", structure)

    runlog_audit = audit_run_logs(selected)
    write_csv(OUT / "case_runlog_audit.csv", runlog_audit)
    artifact_audit = make_artifact_audit(selected, case_cells)
    write_csv(OUT / "case_artifact_paths.csv", artifact_audit)
    evidence_ledger = make_evidence_ledger(selected, runlog_audit, artifact_audit, structure)
    write_csv(OUT / "case_evidence_ledger.csv", evidence_ledger)

    matrix = json.loads((INPUTS / "combined_experiment_matrix.json").read_text(encoding="utf-8-sig"))
    config_map, _, _ = classify_matrix(matrix)
    build_matrix = make_targeted_build_matrix(selected, case_cells, config_map)
    write_csv(ROOT / "evidence" / "targeted_build_matrix.csv", build_matrix)

    report = make_report(
        selected, case_cells, build_metrics, summary["benchmarks"],
        summary["input_audit"], runlog_audit, artifact_audit,
    )
    (OUT / "case_studies.md").write_text(report, encoding="utf-8")
    paper_draft = make_paper_ready_draft(
        selected, case_cells, variant_interactions, structure, runlog_audit,
    )
    (OUT / "paper_ready_draft.md").write_text(paper_draft, encoding="utf-8")

    summary["selected_cases"] = selected
    summary["analysis_code_sha256"] = sha256(Path(__file__).resolve())
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=scalar), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    if "--refresh-cases-only" in sys.argv:
        summary = refresh_case_outputs()
        print(f"Refreshed per-subject max-|Delta| case outputs using {summary['pairwise_result_count']} saved pair results")
    else:
        summary = run_analysis()
        print(f"Wrote {summary['pairwise_result_count']} pair results to {OUT}")
