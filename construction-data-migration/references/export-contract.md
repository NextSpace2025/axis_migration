# Export contract

## Inputs and handoff

Require source scope, a schema version, table/row definitions, field dictionary,
PK/FK constraints, source-to-target mappings, null handling, validation rules,
and an SQL dialect when SQL is requested. Reuse supplied contracts and explicit
user choices. Ask only about missing decisions that change meaning or would
lose data. Ordinary formatting choices do not need another approval step.

Record any optional company mapping/version. A missing company master or
classification map does not prevent raw extraction. Preserve source names and
categories; company-normalized fields may stay null.

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

Deliver the requested CSV/SQL, the contract/mapping used or its identifier,
and a validation report. Include source coverage, table counts, source versus
export totals, checkable/not-checkable counts, unresolved findings, exclusions,
and execution checks actually run. A zero-row input still gets a valid header
or empty table definition plus a clear coverage report.

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
