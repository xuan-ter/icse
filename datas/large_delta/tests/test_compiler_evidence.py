import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_compiler_evidence as evidence


class CompilerEvidenceHelpersTest(unittest.TestCase):
    def test_optimization_remarks_are_summarized_with_local_source_locations(self):
        with tempfile.TemporaryDirectory() as tmp:
            cell = Path(tmp)
            remarks = cell / "remarks"
            remarks.mkdir()
            (remarks / "case.opt.yaml").write_text(
                """--- !Passed
Pass:            inline
Name:            Inlined
DebugLoc:        { File: 'src/hot.rs',
                   Line: 8, Column: 3 }
Function:        hot_function
...
--- !Missed
Pass:            gvn
Name:            NoDefinition
Function:        _ZN12dependency6method17habcdef0123456789E
...
""",
                encoding="utf-8",
            )

            summary = evidence.remark_cell_summary(cell)

        self.assertEqual(summary["remark_records"], 2)
        self.assertEqual(summary["remark_unique_passes"], 2)
        self.assertIn("inline=1", summary["remark_top_passes"])
        self.assertIn("hot_function", summary["remark_function_examples"])
        self.assertIn("src/hot.rs", summary["remark_source_location_examples"])


if __name__ == "__main__":
    unittest.main()
