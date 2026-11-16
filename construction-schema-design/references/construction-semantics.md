# Construction document semantics

Use these interpretation rules only for the document family being inspected.
They do not define a company's accounting taxonomy or authorize cross-document
purchase-order matching.

## Documents and rows

- Distinguish purchase orders, delivery/transaction statements, payment claims,
  tax documents, quotations, and working copies from their contents. A Korean
  `거래명세표` is a transaction statement, not automatically a tax invoice.
- Identify document identity separately from file identity. One document may
  span files; one workbook may contain multiple documents or months.
- A headerless page can continue a document when identifiers, page/row sequence,
  layout, and content provide an unambiguous connection without conflicting
  parties or document numbers. Record the connection and its evidence.
  A filename suffix or a conveniently matching difference alone is insufficient.
- Conflicting or multiple continuation candidates remain unresolved. A reset
  row number or changed date alone does not prove a different document.
- Carry inherited values only within a demonstrated merged cell or document
  group; retain the blank raw cell and the source of the inherited value.
- Classify row roles before aggregating: detail, charge, deduction, subtotal,
  carry-forward, tax, total, or note. Retain repeated real detail rows.
  Do not add subtotals or page carry-forwards to their own underlying details.

## Quantities and specifications

- Keep count, length, area, mass, and time as distinct quantities with units.
  `수량` alone does not establish which quantity was billed.
- Processing, coating, and insulation documents may contain both actual work
  area and a different billed quantity. Preserve a stated work area as area;
  retain pieces, metres, or kilograms separately as billed or auxiliary measures.
  Missing area stays null. Geometry-derived area is a separate derived field
  with a formula and evidence, never a substitute for source-reported work area.
- Determine the pricing basis from labels, units, applicable source rules, and
  arithmetic together. If count and area both fit, do not pick one by coincidence.
- Specifications, thickness, alloy, colour, batch/sequence, location, and
  delivery destination can change a record's meaning. Keep them when observed.
  Preserve `7-2` and multiple sequences as text until a split is justified.
- Unit aliases may be mapped with evidence; dimension changes require a stated
  conversion basis. Never compare mass and area without that basis.

## Amounts, dates, and company settings

- Preserve source amount, calculated amount, and difference separately.
  Define difference as source minus calculated. Missing price or quantity means
  not checkable, not a successful arithmetic check.
- Separate source supply amount, tax, and total. Confirm whether a line price
  includes tax. Do not assume a tax rate, currency, rounding scale, or tolerance.
- A discount or truncation rule needs source/user evidence. A discrepancy alone
  does not authorize manufacturing a balancing adjustment row.
- Preserve source dates and years. Accounting-month adjustments are optional
  company transformations, with original dates and the rule retained.
- Record parties, projects, and classifications as written. Normalized names or
  company codes require a supplied mapping; absent mappings do not block raw
  extraction. A suspected duplicate business identifier is an issue, not proof
  that two suppliers are the same.

## Scope boundaries

Contracts, progress claims, labour, equipment, cost ledgers, and inspections
need their own entity/row definitions. Do not fit every construction document
into a purchase-order line table. Reuse the discovery and validation process,
then design domain-specific tables from the supplied evidence.
