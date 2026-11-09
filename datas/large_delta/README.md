# Large-Delta Reproduction Bundle

This curated bundle preserves the frozen inputs and analysis needed to reproduce the paper's 18-subject maximum-|Δ| results, together with saved compiler and profiling summaries.

## Reproduce the statistical analysis

Requirements: Python 3 and NumPy. From this directory, run:

```powershell
python analyze_large_delta.py
python -m unittest discover -s tests -v
```

`inputs/` contains the frozen snapshots for the 12 real-world workloads, six microbenchmarks, and supporting configuration data. `analyze_large_delta.py` computes the 1,660 pairwise comparisons per subject using 50,000 bootstrap replicates (seed 42), then writes the estimates and case tables under `results/`. The saved interaction results, subject maxima, four-cell medians, audits, and sensitivity results are included. `paper_revision_20261102/tables/big_delta.tex` is the paper table source.

The generated `results/measurement_cell_mapping.csv` is not included because it exceeds GitHub's 100 MB per-file limit; the analysis script regenerates it from the frozen inputs. The machine-specific path reports `case_artifact_paths.csv`, `case_runlog_audit.csv`, and `representative_evidence_status.csv` are also omitted from this curated copy.

## Compiler and profile evidence

`evidence/representative_runs/run_20261023_full_graph/analysis/` contains the saved compiler report, per-module comparison tables, optimization-remark summaries, structure counts, and artifact hashes. The artifact hash manifest, case-selection manifest, and compiler environment are alongside it. The raw `cases/` compiler dumps are not included, so these saved compiler summaries cannot be regenerated from raw compiler artifacts using this bundle alone.

`evidence/hot_paths_wsl_20261105/` preserves the sampled profile evidence and summaries. The `bat_fast/` captures are the source for the approximately 1,000-sample-per-cell statement.

These compiler and profile captures are supplemental observations. The compiler capture used rustc 1.92.0-nightly / LLVM 21.1.2, while the historical runtime records identify rustc 1.98.0-nightly / LLVM 22.1.6 and do not record per-run source revisions. Treat the saved compiler summaries as descriptive evidence; they do not establish a causal mechanism for the historical runtime interaction.
