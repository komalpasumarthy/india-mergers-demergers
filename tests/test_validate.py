"""python3 -m unittest discover tests"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from validate import validate_event, validate_file  # noqa: E402

EX = json.loads((ROOT / "tests" / "example_events.json").read_text())["events"]


def errors(event):
    errs, warns = [], []
    validate_event(event, "t", errs, warns)
    return errs


class ValidateTests(unittest.TestCase):
    def test_examples_pass(self):
        errs, _ = validate_file(ROOT / "tests" / "example_events.json", expect_scheme=False)
        self.assertEqual(errs, [])

    def test_merger_cost_must_sum_to_100(self):
        e = copy.deepcopy(EX[0]); e["legs"][0]["cost_share_pct"] = 90
        self.assertTrue(any("sums to 90" in m for m in errors(e)))

    def test_demerger_cost_below_100(self):
        e = copy.deepcopy(EX[1]); e["legs"][0]["cost_share_pct"] = 100
        self.assertTrue(any("must be < 100" in m for m in errors(e)))

    def test_complete_needs_cost(self):
        e = copy.deepcopy(EX[1]); e["legs"][0]["cost_share_pct"] = None
        self.assertTrue(any("lacks ratio or cost" in m for m in errors(e)))
        e["status"] = "detected"
        self.assertEqual(errors(e), [])

    def test_source_continues(self):
        e = copy.deepcopy(EX[0]); e["source_continues"] = True
        self.assertTrue(any("source_continues false" in m for m in errors(e)))

    def test_bad_isin_checksum(self):
        e = copy.deepcopy(EX[0]); e["source_isin"] = "INE001A01037"
        self.assertTrue(any("check digit" in m for m in errors(e)))

    def test_ratio_format(self):
        e = copy.deepcopy(EX[0]); e["legs"][0]["ratio"] = "42 for 25"
        self.assertTrue(any("held:received" in m for m in errors(e)))

    def test_demerger_has_no_last_trading_date(self):
        e = copy.deepcopy(EX[1]); e["last_trading_date"] = "2025-05-21"
        self.assertTrue(any("null for a DEMERGER" in m for m in errors(e)))

    def test_unknown_key(self):
        e = copy.deepcopy(EX[0]); e["effective_date"] = "2023-07-01"
        self.assertTrue(any("unknown key" in m for m in errors(e)))


if __name__ == "__main__":
    unittest.main()
