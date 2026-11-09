import json
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_large_delta as analysis


class AnalysisHelpersTest(unittest.TestCase):
    def test_literal_all_is_not_normalized_to_none(self):
        self.assertEqual(analysis.clean_label("All"), "All")
        self.assertEqual(analysis.clean_label("None"), "None")

    def test_bh_adjustment_is_monotone_by_rank(self):
        adjusted = analysis.bh_adjust([0.01, 0.04, 0.03, 0.8])
        self.assertAlmostEqual(adjusted[0], 0.04)
        self.assertAlmostEqual(adjusted[1], 0.0533333333, places=8)
        self.assertAlmostEqual(adjusted[2], 0.0533333333, places=8)
        self.assertAlmostEqual(adjusted[3], 0.8)

    def test_generated_matrix_distinguishes_baseline_from_global_ablation(self):
        matrix_path = Path(__file__).resolve().parents[1] / "inputs" / "combined_experiment_matrix.json"
        matrix = json.loads(matrix_path.read_text(encoding="utf-8-sig"))
        mapping, mir_passes, llvm_flags = analysis.classify_matrix(matrix)
        self.assertEqual(mapping["EXP_DBL_000_BASELINE"]["cell"], "00")
        self.assertEqual(mapping["EXP_000_ALL_OFF"]["cell"], "excluded_global_or_nonfactorial")
        self.assertEqual(mapping["EXP_001_DISABLE_ALL"]["cell"], "excluded_global_or_nonfactorial")
        self.assertEqual((len(mir_passes), len(llvm_flags)), (20, 83))
        self.assertEqual(sum(v.get("cell") == "11" for v in mapping.values()), 1660)

    def test_did_sign_matches_paper_convention(self):
        # A joint ablation slower than additivity must produce negative Delta.
        z00, z10, z01, z11 = 0.0, 0.1, 0.2, 0.5
        delta = z10 + z01 - z00 - z11
        self.assertAlmostEqual(delta, -0.2)

    def test_case_selection_picks_each_subject_maximum_without_significance_substitution(self):
        rows = [
            {"benchmark": "rg", "subject_type": "real_world", "mir_pass": f"m{i}",
             "llvm_flag": "cleanups", "delta": value, "abs_delta": abs(value),
             "highlighted": i == 1}
            for i, value in enumerate((0.51, 0.50, 0.49, 0.48, 0.47))
        ]
        rows += [
            {"benchmark": "micro", "subject_type": "microbenchmark", "mir_pass": "m",
             "llvm_flag": "vp", "delta": -0.10, "abs_delta": 0.10,
             "highlighted": True}
        ]
        selected = analysis.select_cases(rows)
        selected_by_benchmark = {row["benchmark"]: row for row in selected}
        self.assertEqual(set(selected_by_benchmark), {"rg", "micro"})
        self.assertEqual(selected_by_benchmark["rg"]["abs_delta"], 0.51)
        self.assertFalse(selected_by_benchmark["rg"]["highlighted"])
        self.assertTrue(selected_by_benchmark["rg"]["selected_as_exploratory"])
        self.assertEqual(selected_by_benchmark["micro"]["abs_delta"], 0.10)

    def test_bootstrap_weights_preserve_sample_size(self):
        weights = analysis.bootstrap_weights(10, 0, 0, 0)
        self.assertEqual(weights.shape, (analysis.BOOTSTRAP_SAMPLES, 10))
        np.testing.assert_array_equal(weights.sum(axis=1), np.full(analysis.BOOTSTRAP_SAMPLES, 10))

    def test_runid_cluster_bootstrap_uses_shared_draws_and_keeps_missing_outcomes(self):
        with patch.object(analysis, "BOOTSTRAP_SAMPLES", 128):
            samples = analysis.paired_boot_means(
                {
                    "B": {"1": 0.1, "2": 0.2, "3": 0.3},
                    "L": {"1": 0.1, "2": 0.2},
                },
                role=3,
                benchmark_index=5,
            )
        self.assertEqual(samples["B"].shape, (128,))
        self.assertEqual(samples["L"].shape, (128,))
        self.assertTrue(np.isfinite(samples["B"]).all())
        self.assertTrue(np.isfinite(samples["L"]).all())
        # Identical observed cluster outcomes yield identical means under the
        # same cluster draws even when one variant has a missing cluster.
        with patch.object(analysis, "BOOTSTRAP_SAMPLES", 128):
            same = analysis.paired_boot_means(
                {"B": {"1": 1.0, "2": 1.0}, "L": {"1": 1.0}},
                role=1,
                benchmark_index=3,
            )
        np.testing.assert_allclose(same["B"], 1.0)
        np.testing.assert_allclose(same["L"], 1.0)

    def test_repeated_build_metadata_is_not_counted_as_independent_builds(self):
        metric = analysis.summarize_repeated_metric(
            [{"CompileTime(s)": "12.5"}, {"CompileTime(s)": "12.5"}, {"CompileTime(s)": "12.5"}],
            ("compile", "time"),
        )
        self.assertEqual(metric["record_count"], 3)
        self.assertEqual(metric["unique_value_count"], 1)
        self.assertEqual(metric["value_if_unique"], 12.5)

        ambiguous = analysis.summarize_repeated_metric(
            [{"CompileTime(s)": "12.5"}, {"CompileTime(s)": "13.0"}],
            ("compile", "time"),
        )
        self.assertEqual(ambiguous["unique_value_count"], 2)
        self.assertEqual(ambiguous["value_if_unique"], "")

    def test_async_variant_rows_share_and_deduplicate_each_runid_build(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir)
            rows = []
            for run_id, compile_time in ((1, 1.0), (2, 2.0), (3, 3.0)):
                for variant in ("B", "L", "S"):
                    rows.append({
                        "ConfigName": "EXP_DBL_000_BASELINE",
                        "Variant": variant,
                        "RunID": str(run_id),
                        "CompileTime(s)": str(compile_time),
                        "BinarySize(Bytes)": "100",
                    })
            with (input_dir / "async.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            case_cells = [
                {
                    "case_role": "test", "benchmark": "async_state_machine_bench",
                    "variant": variant, "cell": "00", "config_id": "EXP_DBL_000_BASELINE",
                }
                for variant in ("B", "L", "S")
            ]
            with patch.object(analysis, "INPUTS", input_dir), patch.object(
                analysis, "ALL_FILES", {"async_state_machine_bench": "async.csv"}
            ):
                metric = analysis.make_case_build_metrics(case_cells)[0]
        self.assertEqual(metric["runtime_rows_with_build_metadata"], 9)
        self.assertEqual(metric["build_count"], 3)
        self.assertEqual(metric["compile_time_median_s"], 2.0)
        self.assertEqual(metric["binary_size_bytes_if_unique"], 100.0)

    def test_csv_writer_keeps_late_optional_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "rows.csv"
            analysis.write_csv(output, [{"role": "first"}, {"role": "hotspot", "top1_count": 50}])
            rows = analysis.read_csv(output)
        self.assertEqual(rows[1]["top1_count"], "50")


if __name__ == "__main__":
    unittest.main()
