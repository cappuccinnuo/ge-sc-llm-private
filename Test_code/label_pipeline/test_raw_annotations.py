"""Unit tests for independently reconstructed raw Dataset A annotations.

Codex 2026-10-10. Temporary fixtures only; no datasets, graph assets or network.
"""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from raw_annotations import _csv_annotation, _records, _source_comparison


class RawAnnotationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "example.sol"
        self.source.write_text("\n".join("line %d" % n for n in range(1, 9)) + "\n",
                               encoding="utf8")

    def csv_fixture(self, rows, header=None):
        if header is None:
            header = ["loc", "length", "bug type", "approach"]
        path = self.root / "BugLog_1.csv"
        with path.open("w", newline="", encoding="utf8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        return path

    def test_csv_bad_integer_or_interval_rejected(self):
        for loc, length in [
            ("0", "1"), ("-1", "1"), ("2.5", "1"), ("oops", "1"),
            ("1", "0"), ("1", "-2"), ("1", "1.2"), ("1", "oops"),
            ("7", "3"), ("9", "1"),
        ]:
            with self.subTest(loc=loc, length=length):
                path = self.csv_fixture([[loc, length, "Re-erntrancy", "code snippet injection"]])
                with self.assertRaises(ValueError):
                    _csv_annotation(path, self.source, "reentrancy")

    def test_csv_missing_column_rejected(self):
        path = self.csv_fixture([["2", "Re-erntrancy", "code snippet injection"]],
                                ["loc", "bug type", "approach"])
        with self.assertRaisesRegex(ValueError, "header"):
            _csv_annotation(path, self.source, "reentrancy")

    def test_csv_missing_row_value_rejected(self):
        path = self.csv_fixture([["2", "3", "Re-erntrancy"]])
        with self.assertRaisesRegex(ValueError, "Malformed CSV row"):
            _csv_annotation(path, self.source, "reentrancy")

    def test_csv_empty_log_rejected(self):
        path = self.csv_fixture([])
        with self.assertRaisesRegex(ValueError, "Empty BugLog"):
            _csv_annotation(path, self.source, "reentrancy")

    def test_duplicate_and_overlap_preserve_union_and_report_counts(self):
        rows = [
            ["2", "3", "Re-erntrancy", "code snippet injection"],
            ["2", "3", "Re-erntrancy", "code snippet injection"],
            ["4", "2", "Re-erntrancy", "code snippet injection"],
        ]
        records, audit = _csv_annotation(self.csv_fixture(rows), self.source, "reentrancy")
        self.assertEqual(records, [{"category": "reentrancy", "lines": [2, 3, 4, 5]}])
        self.assertEqual(audit["csv_rows"], 3)
        self.assertEqual(audit["duplicate_csv_rows"], 1)
        self.assertEqual(audit["duplicate_intervals"], 1)
        self.assertEqual(audit["overlapping_annotation_lines"], 3)
        self.assertEqual(audit["duplicate_line_occurrences"], 4)
        self.assertEqual(audit["annotation_lines"], 4)

    def test_anonymous_fifth_column_is_evidence_not_coordinates(self):
        path = self.csv_fixture(
            [["2", "2", "tx.origin", "code snippet injection", "200"]],
            ["loc", "length", "bug type", "approach", ""],
        )
        records, audit = _csv_annotation(path, self.source, "access_control")
        self.assertEqual(records, [{"category": "access_control", "lines": [2, 3]}])
        self.assertFalse(audit["extra_column_used_as_coordinates"])
        self.assertEqual(audit["extra_anonymous_column"], [{"csv_row": 2, "value": "200"}])

    def source_pair(self, local, canonical):
        a, b = self.root / "local.sol", self.root / "canonical.sol"
        a.write_text(local, encoding="utf8")
        b.write_text(canonical, encoding="utf8")
        return a, b

    def test_source_comment_and_blank_lines_allowed(self):
        a, b = self.source_pair(
            "// revised comment\n\npragma solidity ^0.4.19;\ncontract C { uint x; }\n",
            "// original\npragma solidity ^0.4.19;\ncontract C { uint x; }\n",
        )
        audit = _source_comparison(a, b)
        self.assertEqual(audit["source_comparison"],
                         "comments_or_blank_lines_only_same_preprocessed_text")
        self.assertEqual(audit["mapping_basis"], "canonical_source_original_1based")
        self.assertNotEqual(audit["local_sha256"], audit["canonical_sha256"])
        self.assertTrue(audit["changed_original_line_ranges"])
        self.assertEqual(audit["local_preprocessed_lines"], audit["canonical_preprocessed_lines"])

    def test_source_pragma_with_inline_comment_allowed(self):
        a, b = self.source_pair(
            "pragma solidity >=0.4.11;\ncontract C { uint x; }\n",
            "pragma solidity ^0.4.11; /* originally >=0.4.11 */\ncontract C { uint x; }\n",
        )
        audit = _source_comparison(a, b)
        self.assertEqual(audit["source_comparison"],
                         "pragma_and_comments_only_same_preprocessed_positions")

    def test_source_executable_change_rejected_even_with_pragma_change(self):
        a, b = self.source_pair(
            "pragma solidity >=0.4.11;\ncontract C { uint x = 2; }\n",
            "pragma solidity ^0.4.11;\ncontract C { uint x = 1; }\n",
        )
        with self.assertRaisesRegex(ValueError, "differs beyond"):
            _source_comparison(a, b)

    def test_source_string_change_is_not_treated_as_comment(self):
        a, b = self.source_pair(
            'pragma solidity ^0.4.19;\ncontract C { string x = "// new"; }\n',
            'pragma solidity ^0.4.19;\ncontract C { string x = "// old"; }\n',
        )
        with self.assertRaises(ValueError):
            _source_comparison(a, b)

    def test_source_pragma_moved_across_code_rejected(self):
        a, b = self.source_pair(
            "contract C {}\npragma solidity ^0.4.19;\n",
            "pragma solidity ^0.4.19;\ncontract C {}\n",
        )
        with self.assertRaises(ValueError):
            _source_comparison(a, b)

    def test_records_filter_category_and_deduplicate_lines(self):
        mixed = [
            {"category": "reentrancy", "lines": [3, 2, 2]},
            {"category": "access_control", "lines": [5]},
            {"category": "reentrancy", "lines": [2, 3]},
        ]
        self.assertEqual(_records(mixed, "reentrancy", self.source),
                         [{"category": "reentrancy", "lines": [2, 3]}])
        self.assertEqual(_records(mixed, "arithmetic", self.source), [])

    def test_selected_category_bad_source_lines_rejected(self):
        for lines in ([0], [9], [-1], ["2"], [True], []):
            with self.subTest(lines=lines):
                with self.assertRaises(ValueError):
                    _records([{"category": "reentrancy", "lines": lines}],
                             "reentrancy", self.source)


if __name__ == "__main__":
    unittest.main()
