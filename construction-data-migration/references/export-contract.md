# Export contract

## Inputs and handoff

Require requested source scope, a defined model/version and decision basis,
table/row definitions, field dictionary, PK/FK, source mappings, null handling,
validation rules, and an SQL dialect when requested. Reuse supplied contracts
and explicit user choices, checking their fit against the current contents.
Ask only about missing decisions that change meaning or lose data.

The handoff must account for every requested file and page/sheet, with region/
field mappings or located gaps. Carry `typed_mapped` (structured destination),
`raw_only` (evidence without a business destination), `unresolved` (unread or
uncertain content/mapping) and `excluded` (reasoned scope/non-business exclusion).
If the design skill is unavailable, perform this review before conversion using
the supplied target and actual sources. Include uninspected content; a sample
is not full coverage. Raw-only and excluded content never count as mapped.
Resolve structural ambiguity before converting that scope; representable source
uncertainty may remain null plus issues. Report partial results without silently
narrowing the request. Model definition does not authorize unrequested exports.

Record any optional company mapping/version. A missing company master or
classification map does not prevent raw extraction. Preserve source names and
categories; company-normalized fields may stay null.

Classification outputs use the leading contract order `company_name`,
`major_category` (construction trade), `middle_category` (activity),
`minor_category` (specific operation), `classification_basis`, `source_reference`.
Company is the counterparty, excluding the reference buyer. Verify the defined
classification mapping/version, hierarchy and source evidence. Keep proposed or
unresolved classifications separate from confirmed company values; do not
silently promote a starter suggestion. Other business tables retain their own
contract column order.

Keep trade classification at three levels and preserve the defined shared
metadata and document-type-specific detail schemas. Verify that each subdivided
source attribute has a mapping to located wording/layout/units, with the original
text retained. Missing source evidence cannot be replaced with assumptions from
paths, company names or industry defaults. Label derived fields separately with
their rules/input references; report new meanings for model review rather than
adding columns or flattening incompatible document types during export.

## CSV

- Export one CSV per table in contract column order, with a header, UTF-8 BOM,
  standard CSV quoting, and no thousands separators in numeric fields.
- Use canonical decimal strings and ISO dates only when fully known. Keep
  unknown/partial dates in raw data and flag them rather than inventing dates.
- Use `\N` for null. For every non-null field, double literal backslashes
  before CSV quoting; on reading, recognize the exact null token first, then
  undouble backslashes. This distinguishes null, empty text, and literal `\N`.
- CSV text beginning with `=`, `+`, `-`, or `@` can be interpreted as a formula
  by a spreadsheet. Preserve raw data, identify affected free-text fields, and
  recommend importing them as text. If requested, create a separately labelled
  spreadsheet-safe presentation copy; never silently alter the migration data.

## Standalone SQL

- Honour the target dialect. Default to SQLite only when no target is supplied,
  and state that default in the report. Do not promise universal SQL syntax.
- Use explicit table definitions, PK/FK, required constraints, and column-named
  INSERT statements in a transaction. Insert parents before children. In SQLite,
  enable foreign keys before starting the transaction.
- Target a new empty database by default. Do not add DROP, DELETE, TRUNCATE,
  REPLACE, conflict-ignore, or an unrequested upsert to make a rerun succeed.
  An existing-table conflict should stop with a clear remedy: use an empty
  scratch database or request an explicitly designed merge workflow.
- Use validated contract identifiers with dialect-correct quoting where needed;
  never interpolate raw source labels as SQL identifiers. Encode values as SQL
  literals using a library/dialect-aware serializer, or parameter binding when
  populating a scratch database. A document value must never become raw SQL.
  Handle apostrophes, newlines, backslashes, Unicode, and null explicitly.
  For SQLite text containing NUL, reject the unsupported value to review output
  or use an explicitly designed binary representation; never truncate it.
- Validate decimals with decimal arithmetic, not binary floats. Use exact
  NUMERIC/DECIMAL where the database supports it. SQLite NUMERIC affinity is not
  an exact-decimal guarantee: this example stores decimals as canonical TEXT.
  An explicitly established currency scale also permits integer minor units.
- The example uses export-local IDs, no credentials, no server connection,
  and no environment variables. Never invent business IDs from a presumed match.

## Validation and exception handling

Keep these findings distinguishable, recording affected locations and checks
actually performed. Use `not_checked` or `not_checkable` with reasons rather
than treating missing evidence as a pass:

| Check | What establishes it |
|---|---|
| Source-reading accuracy | Compare extracted values and row boundaries with actual cells/pages/images; record OCR, visual-reading and formula-cache limits |
| Semantic mapping | Verify field meanings, quantity/unit/pricing roles, group inheritance, document relationships and coverage against the defined model |
| Source-internal consistency | Preserve conflicting labels, formulas, amounts or summaries independently; copying a conflict accurately does not resolve it |
| Arithmetic | Recalculate only from evidenced bases, units and rounding; retain source amount, calculated amount and source-minus-calculated difference |
| Database integrity | Check types, nulls, keys, ownership and read-back in the requested isolated local target |

Agreement of totals does not prove OCR or mapping accuracy. A copied source
error remains a source finding, not an excuse to overwrite the source value.

1. Account for every requested source, page/sheet, and row: exported, non-detail,
   duplicate-copy occurrence, unreadable, or excluded with a located reason.
2. Validate field types, actual calendar dates, decimal precision, unit meaning,
   required fields, unique keys, and document/line ownership for every FK.
3. Recalculate only where quantity, price, pricing basis, and rounding are
   established. Missing basis is not checkable. Do not assume tolerance or tax.
4. Reconcile detail/charge/deduction totals against source subtotals and document
   totals without counting summary rows twice. Report source minus calculated.
5. Preserve mismatches and partial data visibly. Do not infer a correction,
   adjustment, new category, supplier identity, or missing quantity to force a pass.
6. Load generated SQL only into an isolated disposable database, if available.
   Read back counts, values, nulls, decimals, Unicode, duplicate real rows, and
   FK checks. Test an invalid FK and a duplicate key fail. If the target runtime
   is unavailable, label that dialect's execution unverified.
7. Existing outputs stay intact on failure. Preserve review outputs and explain
   the cause and remedy. A retry must use the same contract and explicit scope;
   never use it to bypass a validation failure or broaden a write operation.

## Report and run log

Deliver requested outputs, model/version and decision basis, the mappings and
coverage review used, and a validation report. Include requested versus processed
scope, coverage statuses, table counts, source versus export totals, results for
each check category, checkable/not-checkable counts, unresolved findings and
exclusions. Keep model coverage, conversion and validation completion separate.
A zero-row input still gets a valid header or empty table definition plus an
honest coverage report.

Write a small JSONL run log alongside generated exports when file output is
requested. Each event includes `timestamp` (UTC ISO), `action`, `input`
(source identifiers/counts, not source contents), `result` (counts/status), and
`error` (null or a redacted cause and remedy). Keep credentials, account data,
full source rows, and absolute private paths out of logs. No hosted service,
telemetry, or API key is required by these skills.

The worked example's `validation_issues` table records source findings;
execution events belong to the run log rather than business rows.

## Sources

- [SQLite datatypes](https://sqlite.org/datatype3.html): storage classes and
  affinity, including numeric conversion behavior.
- [SQLite foreign keys](https://sqlite.org/foreignkeys.html): enabling and
  checking relationship enforcement.
