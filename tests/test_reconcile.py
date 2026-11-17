"""Reconciliation tests using fictional values only."""

import importlib.util
import json
from decimal import Decimal
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

# Major variable: the source root remains independent of the test runner's cwd.
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("reconcile", ROOT / "scripts/reconcile.py")
RECONCILE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECONCILE)

# Major variable: the fictional worked example from the matching contract.
EXAMPLE = {
    "statement": {
        "lines": [
            {"line_id": "1", "quantity": "52.37", "unit_price": "7300", "amount": "382300"},
            {"line_id": "2", "quantity": "118.20", "unit_price": "7300", "amount": "862800"}],
        "supply_amount": "1245100", "tax_amount": "124510", "total_amount": "1369610",
        "tax_rate": "0.1", "written_amount": "일금 일백삼십육만구천육백십 원정"},
    "order_rounds": [
        {"round": "R2", "count": "40", "measure": "52.36549"},
        {"round": "R3", "count": "90", "measure": "118.20410"},
        {"round": "R4", "count": "2", "measure": "1.10230"}],
    "links": [
        {"round": "R2", "statement_line_id": "1", "statement_count": "40",
         "statement_measure": "52.37", "group": "insulation"},
        {"round": "R3", "statement_line_id": "2", "statement_count": "90",
         "statement_measure": "118.20", "group": "insulation"}]}


def codes(result):
    """Method: list finding codes in order."""
    return [row["code"] for row in result["findings"]]


class ReconcileTests(unittest.TestCase):
    """Class: verify arithmetic, totals, cumulative and open-item behaviour."""

    def test_worked_example(self):
        """Method: truncation is detected, totals pass and the last round stays open."""
        result = RECONCILE.reconcile(EXAMPLE)
        truncated = [row for row in result["findings"] if row["code"] == "amount_truncated"]
        self.assertEqual([row["difference"] for row in truncated], ["-1", "-60"])
        self.assertEqual(result["checks"]["lines"]["truncation_unit"], "100")
        for name in ("supply_vs_line_sum", "total_vs_supply_plus_tax", "tax_vs_rate", "written_amount"):
            self.assertEqual(result["checks"][name], "pass")
        self.assertEqual([item["status"] for item in result["open_items"]],
                         ["matched", "matched", "unbilled"])
        self.assertNotIn("quantity_mismatch", codes(result))
        self.assertNotIn("amount_difference", codes(result))

    def test_inconsistent_line_is_a_difference_not_truncation(self):
        """Method: one line outside the pattern prevents a truncation claim."""
        lines = [{"quantity": "52.37", "unit_price": "7300", "amount": "382300"},
                 {"quantity": "118.20", "unit_price": "7300", "amount": "860000"}]
        _, findings = RECONCILE.check_lines(lines)
        self.assertEqual([row["code"] for row in findings], ["amount_difference", "amount_difference"])

    def test_single_line_cannot_establish_a_pattern(self):
        """Method: a lone truncated line is reported as a plain difference."""
        summary, findings = RECONCILE.check_lines(
            [{"quantity": "52.37", "unit_price": "7300", "amount": "382300"}])
        self.assertIsNone(summary["truncation_unit"])
        self.assertEqual(findings[0]["code"], "amount_difference")

    def test_exact_rounded_and_uncheckable_lines(self):
        """Method: exact lines pass, won rounding is noted, missing basis is not checkable."""
        summary, findings = RECONCILE.check_lines([
            {"quantity": "2", "unit_price": "300", "amount": "600"},
            {"quantity": "1.5", "unit_price": "333", "amount": "500"},
            {"amount": "50"}])
        self.assertEqual([row["code"] for row in findings],
                         ["amount_not_checkable", "rounding_difference"])
        self.assertEqual(summary["lines_not_checkable"], 1)
        self.assertEqual(summary["line_sum"], "1150")

    def test_totals_findings_and_unstated_tax_rate(self):
        """Method: wrong totals are findings; tax is not assumed without a rate."""
        statement = {"lines": [{"amount": "600"}], "supply_amount": "650",
                     "tax_amount": "65", "total_amount": "700", "written_amount": "칠백십오원"}
        checks, findings = RECONCILE.check_totals(statement)
        self.assertEqual(checks["tax_vs_rate"], "not_checked")
        self.assertEqual([row["code"] for row in findings],
                         ["total_difference", "total_difference", "written_amount_difference"])
        checks, findings = RECONCILE.check_totals(
            {"lines": [], "supply_amount": "1000", "tax_amount": "90", "tax_rate": "0.1"})
        self.assertEqual(findings[-1]["code"], "tax_difference")
        self.assertEqual(checks["total_vs_supply_plus_tax"], "not_checkable")

    def test_korean_written_amounts(self):
        """Method: parse common forms and refuse unreadable text."""
        cases = {"일금 삼백오십만 원정": 3500000, "천이백원": 1200, "십만 원": 100000,
                 "일억이천삼백사십오만육천칠백팔십구": 123456789, "만 원": 10000}
        for written, expected in cases.items():
            self.assertEqual(RECONCILE.parse_korean_amount(written), Decimal(expected))
        self.assertIsNone(RECONCILE.parse_korean_amount("약 3백만원"))

    def test_cumulative_inconsistency(self):
        """Method: a printed cumulative that skips a round is reported with both values."""
        rounds = [{"round": 1, "count": "10", "measure": "5.5", "cumulative_count": "10"},
                  {"round": 2, "count": "20", "measure": "7.5", "cumulative_count": "30",
                   "cumulative_measure": "13.0"},
                  {"round": 3, "count": "5", "measure": "1", "cumulative_count": "15"}]
        findings = RECONCILE.check_cumulative(rounds)
        self.assertEqual(len(findings), 1)
        self.assertEqual((findings[0]["source_value"], findings[0]["compared_value"]), ("15", "35"))

    def test_partial_over_and_grouped_open_items(self):
        """Method: partial sums, overbilling and separate billing groups stay distinct."""
        rounds = [{"round": "A", "count": "10", "measure": "100.004"},
                  {"round": "B", "count": "4"}]
        links = [{"round": "A", "statement_measure": "60.00", "group": "fabricator"},
                 {"round": "A", "statement_measure": "40.00", "group": "fabricator"},
                 {"round": "A", "statement_measure": "70.00", "group": "finisher"},
                 {"round": "B", "statement_count": "5", "group": "finisher"}]
        open_items, _ = RECONCILE.check_links(rounds, links)
        status = {(item["group"], item["round"]): item["status"] for item in open_items}
        self.assertEqual(status, {("fabricator", "A"): "matched", ("fabricator", "B"): "unbilled",
                                  ("finisher", "A"): "partially_billed",
                                  ("finisher", "B"): "overbilled"})
        remaining = {(item["group"], item["round"]): item["remaining"] for item in open_items}
        self.assertEqual(remaining[("finisher", "A")], "30")

    def test_count_matches_but_measure_differs(self):
        """Method: equal pieces with a different area is a quantity mismatch."""
        _, findings = RECONCILE.check_links(
            [{"round": 1, "count": "10", "measure": "25.004"}],
            [{"round": 1, "statement_count": "10", "statement_measure": "26.00"}])
        self.assertEqual([row["code"] for row in findings], ["quantity_mismatch"])

    def test_no_links_lists_every_round_unbilled(self):
        """Method: order rounds without any statement remain open items."""
        open_items, findings = RECONCILE.check_links([{"round": 1, "count": "3"}], [])
        self.assertEqual((open_items[0]["status"], open_items[0]["remaining"]), ("unbilled", "3"))
        self.assertEqual(findings, [])

    def test_invalid_inputs_are_rejected(self):
        """Method: floats, bad numbers and unknown rounds stop with a clear error."""
        with self.assertRaises(ValueError):
            RECONCILE.to_decimal(0.1)
        with self.assertRaises(ValueError):
            RECONCILE.check_lines([{"quantity": "abc", "unit_price": "1", "amount": "1"}])
        with self.assertRaises(ValueError):
            RECONCILE.check_links([{"round": 1, "count": "1"}], [{"round": 9}])
        with self.assertRaises(ValueError):
            RECONCILE.reconcile([])

    def test_cli_reads_json_numbers_exactly_and_redacts_errors(self):
        """Method: JSON numbers stay exact; failures hide paths and give a remedy."""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            source.write_text('{"statement": {"lines": [{"quantity": 0.1, "unit_price": 3, '
                              '"amount": 0.3}], "supply_amount": 0.3}}', encoding="utf-8")
            script = str(ROOT / "scripts/reconcile.py")
            done = subprocess.run([sys.executable, script, str(source)],
                                  capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(done.returncode, 0)
            self.assertEqual(json.loads(done.stdout)["findings"], [])
            source.write_text("{broken", encoding="utf-8")
            failed = subprocess.run([sys.executable, script, str(source)],
                                    capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(failed.returncode, 1)
            error = json.loads(failed.stdout)["error"]
            self.assertTrue(error["cause"] and error["resolution"])
            self.assertNotIn(directory, failed.stdout)


if __name__ == "__main__":
    unittest.main()

# 동작 설명: 가상의 숫자로 절사 판별, 합계·부가세·한글 금액 검산, 누계 오류,
# 미청구·부분청구·과청구 판정과 잘못된 입력 처리를 확인합니다.
