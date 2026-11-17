# Synthetic export validation walkthrough

This example contains fictional data only. The reproducible checks are in
`tests/test_synthetic_export.py` at the package root. It demonstrates the
SQLite export contract; it does not establish OCR accuracy or live migration.

## Scope and contract

- Contract: procurement-example-v1, standalone SQLite, fresh empty database.
- Sources: `example-order.txt` and `example-statement.txt`, both included here.
- Coverage: two document headers/totals and four numbered source rows.
- No company classification mapping or external master is provided.
- No purchase-order/statement relationship is asserted or created.

The supplied `procurement-example-v1` model is defined for these two text
fixtures and their headers/totals/numbered rows. Its decision basis is the
explicit worked contract in the design skill, not inferred ERP compatibility.
This example demonstrates conversion after review; generating SQL does not
itself define or approve an unreviewed model.

| Source region | Model destination | Coverage status |
|---|---|---|
| Both document headers and totals | `documents`, document-level `source_references` | `typed_mapped` |
| Two order rows | `document_lines`, line-level `source_references` | `typed_mapped` |
| Statement processing and charge rows | `document_lines`, line-level `source_references` | `typed_mapped` |
| Explanatory fixture notes | Retained in original text; outside transaction columns | `excluded`: instructions about the fictional example, not additional transactions |

The amount-only charge is structurally represented even though multiplication
is not checkable. No extra page/sheet or industry layout is implied by this
review. Additional unread material would be `unresolved`; saving an unmapped
ledger as text would be `raw_only`, not additional business-model coverage.

## Expected output

| Table | Rows | Meaning |
|---|---:|---|
| `documents` | 2 | One independent order and one independent statement |
| `document_lines` | 4 | Three detail rows and one charge row |
| `source_references` | 6 | Two document locations and four row locations |
| `validation_issues` | 1 | One amount-only charge is not checkable by multiplication |

Companion CSVs have the same table names and column order as the SQL. Their
encoding is UTF-8 BOM, with `\N` for null and doubled literal backslashes for
non-null text. The SQL stores exact decimals as canonical TEXT.

## Normal and edge cases

- Order: two distinct rows, each `2 SHEET × 300 = 600`; supply `1200`, tax `120`,
  total `1320`. Both rows remain even though their visible values are identical.
- Statement detail: reported work area `4.5 m²`, billed quantity `6 EA`, price
  `100`, amount `600`. Area does not replace billed quantity.
- Statement charge: quantity, unit, price, and work area are null; amount `50`
  remains. Cause: missing quantity/price. Remedy: obtain a pricing basis if a
  multiplication check is required; do not fabricate values.
- Statement: detail plus charge gives supply `650`; source tax `65` gives total
  `715`. Tax is taken from this source, not generated from a default tax rule.
- Source Korean labels, blank strings, and `O'Brien finish` survive the SQL and
  CSV round trips. Company categories stay null without a supplied map.

## Failure cases

The database rejects orphan lines, a source/issue linked to a line from another
document, duplicate line numbers within one document, and non-positive line
numbers. Rerunning the standalone SQL against existing tables fails without
erasing the original rows. A fresh scratch database is the remedy.

The public-release tests also reject unsafe manifest paths and symlinks,
exclude unlisted private material, and preserve an existing release ZIP.

## Checks requiring a real agent/source environment

The text-fixture tests compare source values and SQL/CSV mappings, verify
arithmetic where possible, and exercise database constraints/read-back. They
do not test image/OCR accuracy, host capabilities or target-system fit.
In real runs, report these check categories separately, including source-internal
conflicts and not-checked/not-checkable reasons. Mapped does not mean validated.

Use representative PDFs, workbooks, or images to evaluate merged cells,
continuations with competing candidates, incomplete OCR, source subtotals,
unknown columns, full-scope coverage reviews and contract changes. Verify
behavior and located findings, not merely matching prose. Those host
integrations are not exercised by the standard-library fixture tests.
