"""Validate the synthetic export's source meaning, constraints, and CSV round trip."""

import csv
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import unittest

# Major variable: fixtures are fictional and shipped inside the migration skill.
EXAMPLES = (Path(__file__).resolve().parents[1] / "construction-data-migration/assets/examples")


class SyntheticExportTests(unittest.TestCase):
    """Class: verify the starter model with normal, failure, and edge cases."""

    def setUp(self):
        """Method: execute the standalone SQL in a fresh in-memory database."""
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript((EXAMPLES / "example.sqlite.sql").read_text(encoding="utf-8"))

    def tearDown(self):
        """Method: dispose of all scratch data after each test."""
        self.connection.close()

    def test_source_rows_totals_and_arithmetic(self):
        """Method: compare raw source rows and declared totals with the export."""
        for file, document_id in (("example-order.txt", "D-PO-1"),
                                  ("example-statement.txt", "D-ST-1")):
            source = (EXAMPLES / file).read_text(encoding="utf-8")
            lines = self.connection.execute(
                "SELECT * FROM document_lines WHERE document_id=? ORDER BY line_number",
                (document_id,)).fetchall()
            source_rows = [row for row in source.splitlines()
                           if row.split(" | ", 1)[0].isdigit()]
            self.assertEqual(len(lines), len(source_rows))
            header = next(row for row in source.splitlines() if row.startswith("Line |"))
            labels = [value.strip() for value in header.split("|")[1:]]
            for raw, exported in zip(source_rows, lines):
                cells = [value.strip() for value in raw.split("|")[1:]]
                self.assertEqual(json.loads(exported["raw_record"]), dict(zip(labels, cells)))
                self.assertEqual(Decimal(exported["amount"]), Decimal(cells[-1]))
            document = self.connection.execute(
                "SELECT * FROM documents WHERE document_id=?", (document_id,)).fetchone()
            for label, field in (("Supply amount", "supply_amount"),
                                 ("Tax amount", "tax_amount"), ("Total amount", "total_amount")):
                value = next(row.split(": ", 1)[1] for row in source.splitlines()
                             if row.startswith(label + ":"))
                self.assertEqual(document[field], value)
            self.assertEqual(sum(Decimal(row["amount"]) for row in lines),
                             Decimal(document["supply_amount"]))
            self.assertEqual(Decimal(document["supply_amount"]) + Decimal(document["tax_amount"]),
                             Decimal(document["total_amount"]))
        rows = self.connection.execute(
            "SELECT billed_quantity, unit_price, amount FROM document_lines WHERE unit_price IS NOT NULL")
        for row in rows:
            self.assertEqual(Decimal(row[0]) * Decimal(row[1]), Decimal(row[2]))

    def test_quantity_roles_nulls_unicode_and_apostrophe(self):
        """Method: retain area, billing basis, missing fields, and source text."""
        row = self.connection.execute("SELECT * FROM document_lines WHERE line_id='L-ST-1'").fetchone()
        self.assertEqual((row["work_area"], row["billed_quantity"], row["billed_unit"]),
                         ("4.5", "6", "EA"))
        self.assertEqual(row["specification"], "O'Brien finish")
        self.assertEqual(json.loads(row["raw_record"])["면적(㎡)"], "4.5")
        charge = self.connection.execute("SELECT * FROM document_lines WHERE line_id='L-ST-2'").fetchone()
        for field in ("work_area", "billed_quantity", "billed_unit", "unit_price", "company_category"):
            self.assertIsNone(charge[field])
        self.assertEqual(charge["amount"], "50")
        self.assertEqual(self.connection.execute("SELECT count(*) FROM validation_issues").fetchone()[0], 1)
        self.assertEqual(self.connection.execute(
            "SELECT count(*) FROM document_lines WHERE company_category IS NOT NULL").fetchone()[0], 0)

    def test_repeated_real_rows_and_provenance(self):
        """Method: keep distinct repeated details and locate every document and line."""
        self.assertEqual(self.connection.execute(
            "SELECT count(*) FROM document_lines WHERE document_id='D-PO-1' AND amount='600'").fetchone()[0], 2)
        self.assertFalse(self.connection.execute(
            "SELECT 1 FROM document_lines l WHERE NOT EXISTS "
            "(SELECT 1 FROM source_references r WHERE r.line_id=l.line_id)").fetchall())
        self.assertFalse(self.connection.execute(
            "SELECT 1 FROM documents d WHERE NOT EXISTS "
            "(SELECT 1 FROM source_references r WHERE r.document_id=d.document_id AND r.line_id IS NULL)").fetchall())
        for reference in self.connection.execute("SELECT source_file FROM source_references"):
            self.assertTrue((EXAMPLES / reference[0]).is_file())
        self.assertFalse(self.connection.execute("PRAGMA foreign_key_check").fetchall())

    def test_invalid_relationships_and_keys_fail(self):
        """Method: reject orphans, cross-document links, and duplicate numbered rows."""
        statements = [
            "INSERT INTO document_lines (line_id,document_id,line_number,row_type,raw_record) VALUES ('BAD','MISSING',1,'detail','{}')",
            "INSERT INTO source_references VALUES ('BAD','D-PO-1','L-ST-1','x','row 1',NULL)",
            "INSERT INTO validation_issues VALUES ('BAD','D-PO-1','L-ST-1','x','cause','remedy')",
            "INSERT INTO document_lines (line_id,document_id,line_number,row_type,raw_record) VALUES ('BAD','D-PO-1',1,'detail','{}')",
            "INSERT INTO document_lines (line_id,document_id,line_number,row_type,raw_record) VALUES ('BAD','D-PO-1',0,'detail','{}')"]
        for statement in statements:
            with self.subTest(statement=statement):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(statement)
                self.connection.rollback()

    def test_sql_rerun_fails_without_erasing_data(self):
        """Method: an existing database is not silently overwritten or merged."""
        with self.assertRaises(sqlite3.OperationalError):
            self.connection.executescript((EXAMPLES / "example.sqlite.sql").read_text(encoding="utf-8"))
        self.connection.rollback()
        self.assertEqual(self.connection.execute("SELECT count(*) FROM document_lines").fetchone()[0], 4)

    def test_empty_document_and_exact_decimal_text(self):
        """Method: represent a header-only document and preserve decimal precision."""
        self.connection.execute(
            "INSERT INTO documents (document_id,document_type) VALUES ('EMPTY','transaction_statement')")
        self.connection.execute(
            "INSERT INTO source_references VALUES ('R-EMPTY','EMPTY',NULL,'empty.txt','header',NULL)")
        self.assertEqual(self.connection.execute(
            "SELECT count(*) FROM document_lines WHERE document_id='EMPTY'").fetchone()[0], 0)
        self.assertIsNone(self.connection.execute(
            "SELECT total_amount FROM documents WHERE document_id='EMPTY'").fetchone()[0])
        value = "0.1000000000000000001"
        self.connection.execute("UPDATE document_lines SET work_area=? WHERE line_id='L-ST-1'", (value,))
        self.assertEqual(self.connection.execute(
            "SELECT work_area FROM document_lines WHERE line_id='L-ST-1'").fetchone()[0], value)

    def test_csv_matches_sql_with_reversible_null_encoding(self):
        """Method: compare every CSV cell, including nulls and exact decimals."""
        for table in ("documents", "document_lines", "source_references", "validation_issues"):
            cursor = self.connection.execute(f'SELECT * FROM "{table}" ORDER BY 1')
            expected = [[None if value is None else str(value) for value in row] for row in cursor]
            with (EXAMPLES / f"{table}.csv").open(encoding="utf-8-sig", newline="") as source:
                reader = csv.reader(source)
                self.assertEqual(next(reader), [column[0] for column in cursor.description])
                actual = [[None if value == "\\N" else value.replace("\\\\", "\\")
                           for value in row] for row in reader]
            self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()

# 동작 설명: 가상 원문과 SQL·CSV를 비교하고 수량 구분과 누락값 보존을 확인합니다.
# 잘못된 관계와 중복 키의 거부, 실제 반복행의 보존도 검사합니다.
