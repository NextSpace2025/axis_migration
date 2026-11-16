# From user intent to a useful table

## Required sequence

Read the request and files together. The same document can support different
tables; the intended use determines row grain and which fields are visible.
Inspect actual sheet cells or PDF/image pages, including headers, merged groups,
units and footnotes. File inventories and OCR text dumps are intermediate work.

1. Restate the intended result in one sentence, using established context.
2. Inspect representative layouts and propose ordered display headers, database
   names, types, units, null rules, and source locations for each proposed field.
3. Explain which columns are observed, normalized, or derived. Keep optional
   company classification separate from factual document fields.
4. Show a few actual rearranged source rows. Do not use fictional data in place
   of supplied files when demonstrating whether a mapping works.
5. Review ambiguities and continue with migration when the user requested the
   work and the mapping is clear. Do not turn every header proposal into a new
   approval gate. Ask only for decisions that change meaning or discard data.

## Different intents, different headers

These are fictional examples of proposals, not mandatory templates.

| User intent | Grain | Possible display headers |
|---|---|---|
| Organize purchased materials | One source item occurrence | Document date, supplier, site, item, specification, quantity, unit, unit price, amount |
| Preserve processing work and billing | One work/billing item occurrence | Date, site, sequence, item, reported work area, billed quantity, billed unit, price, amount |
| Organize equipment rental records | One equipment/usage source row | Site, equipment model, equipment ID, period start, period end, days, rate basis, price, amount |

For example, a fictional source row `품명=Panel; 면적=4.5; 수량=6;
단위=EA; 단가=100; 금액=600` becomes separate work-area and billed-quantity
columns when the intent requires both. A request to organize equipment rental
does not justify using that area-based layout or assuming days × monthly rate.

## Handoff and completion boundary

Record the purpose, grain, ordered display headers, database fields, field-level
source mappings, and representative rows in `structure.md`. Identify the primary
business table to display. Preserve provenance in supporting tables.

Do not deliver `cells_json`, text-line lists, or a file inventory as the user's
final business table. If a source cannot be interpreted, preserve its raw evidence
and report an explicit incomplete item; continue processing other readable files.
Scope limitations are findings, not a reason to silently replace the requested
transformation with raw extraction. The existing starter ERD is illustrative:
adapt it to the observed data and requested purpose.
