# From document evidence to a data model

## Required sequence

Derive business questions from located evidence and relationships in each run.
Amount, material and legal-document review are examples, never a fixed menu.
For each question show its row grain, the ordered headers needed to answer it,
why those headers belong together, representative original values and locations,
and missing evidence under 추가 확인. For legal documents describe the terms
actually present. A source can support several questions. Reuse the same mapping
and approval decision wherever a header appears. In the review, link a question
to its supporting files and a file back to all questions it supports.

1. Inventory the requested files, then inspect actual cells or PDF/image pages,
   including headers, merged groups, units and footnotes. Use the stated purpose
   if available; its absence does not block discovering the records' structure.
2. Map statement/order text and labels to candidate meanings, resolve supplier
   versus reference-buyer roles, and group recurring terms by counterparty before
   proposing the [trade/activity/operation hierarchy](classification-guide.md).
   Identify document types, business activities, quantities, pricing bases and
   relationships. Industry knowledge supplies hypotheses; source content supplies
   evidence. Keep optional company classification separate from both.
3. Propose entities, row meanings, relationships and ordered headers with types,
   units, null rules and source locations. Explain which fields are observed,
   normalized or derived, and which functions the records suggest. Show actual
   rearranged source rows, not fictional replacements for supplied files.
4. Review the full requested material against the model using the coverage
   statuses in [the design contract](design-contract.md). New layouts and
   unrepresented meanings revise the proposal. Mark uninspected material
   unresolved; raw text preservation alone does not prove model fit.
5. Record the model version, reviewed scope, gaps and decision basis. Continue
   with conversion only when requested and the model is defined for that scope.
   Ask for material meaning/loss decisions, not a new approval for every header.

A filename or familiar header is a clue, not a definition. A column headed
`m2` can contain metres or per-piece charges; inspect values, units, formulas
and surrounding groups before assigning the pricing basis. Read native Excel
cells and usable PDF text directly; image/OCR reading is a means of obtaining
evidence, not a requirement to OCR every file or a guarantee of correct numbers.

## Content-first classification and table reconstruction

Use this workflow when folder placement, file names or source layouts are
inconsistent. Rearrangement means new structured records in separate outputs;
do not move, rename, overwrite or save changes to source documents. Keep the
private folder record as specified by the skill, excluded from source discovery.

1. **Inventory and read evidence.** Inventory all requested files recursively,
   excluding prior outputs and the private record. Retain relative source paths
   and file fingerprints so identical copies can be identified without deleting
   originals. Start with representative layouts to develop the interpretation,
   then account for every requested file/page/sheet in the coverage review.
   Extract source values with their locations and surrounding labels before
   normalizing them. The evidence layer need not be a separate database or export.
2. **Choose the reading method per region.** For XLSX/XLS use available native
   cells, sheet names, merged ranges, headers, hidden rows/columns and formulas
   with available cached results. Note stale or missing caches; do not execute
   macros, refresh external links or claim recalculation without performing it.
   Inspect embedded images or image-only regions separately. For PDFs use usable
   text with layout, then inspect image/table regions and apply available OCR or
   visual reading where necessary. Record actual methods and unsupported regions;
   neither OCR of every spreadsheet nor treating all PDF text as complete is a default.
3. **Identify document and table boundaries from content.** Titles, party roles,
   document numbers, dates, headers, units and surrounding text support document
   types and project assignments. A file may contain several documents; a sheet
   may contain several tables. Give each logical document/region a source-local
   identity. Link continuation pages only with evidence and retain their original
   locations. Do not inherit a folder's project/date/company into a confirmed
   business field. Record disagreements between names/paths and content as issues;
   ambiguous classifications stay provisional or unresolved with located evidence.
4. **Reconstruct rows before proposing common columns.** Associate values with
   their actual headers using coordinates and layout, including multirow headers
   and side-by-side blocks. Inherit merged/group labels only within evidenced
   boundaries; record the parent cell. Join wrapped descriptions or split rows
   only with layout/continuation evidence. Keep detail, subtotal, tax, total,
   carry-forward, note and template rows distinguishable. Never fill all blanks
   down across a document boundary or treat a blank as zero. Use formulas as
   supporting meaning evidence, not permission to replace printed source values.
5. **Model and rearrange by meaning.** Group compatible records by document
   family and row meaning, even when scattered across folders. Preserve distinct
   quantity, date and amount roles; a progress claim's cumulative amount is not
   a current-period purchase amount. Propose common columns only where meanings
   agree, with separate tables or typed extensions for other concepts. Preserve
   original strings alongside normalized/derived values and transformation rules.
   Produce real sample rows for model review; bulk business exports follow the
   defined contract only when conversion was requested.
6. **Trace and verify.** Maintain a reconstruction map, within the existing
   source mappings/coverage review, from source file, document/region, page or
   sheet/cell range (image coordinates when available) to document type, target
   table/row/fields, reading method, transformation and issue/status. When one
   output row combines multiple locations, retain every contributing reference.
   Distinguish identical file copies, revised documents and repeated real rows;
   matching names, dates or amounts alone do not establish duplicates. Compare
   reconstructed boundaries and values against actual source regions for each
   encountered layout, then account for all requested scope. Unread or uncertain
   regions remain visible rather than becoming confirmed data.

For example, a fictional `orders/2030-04.xlsx` contains a titled progress claim
with previous/current/cumulative columns. Classify that region as a progress
claim from its contents, record the path conflict, and preserve all three amount
roles. If another sheet contains a transaction statement, classify it separately.
Two visually identical item lines remain two source occurrences unless there is
evidence they are duplicate copies. Do not rename the workbook to correct it.

## Different records, different model needs

These are fictional examples of proposals, not mandatory templates.

| Observed record family | Grain | Possible display headers |
|---|---|---|
| Purchased materials | One source item occurrence | Document date, supplier, site, item, specification, quantity, unit, unit price, amount |
| Processing work and billing | One work/billing item occurrence | Date, site, sequence, item, reported work area, billed quantity, billed unit, price, amount |
| Equipment rental | One equipment/usage source row | Site, equipment model, equipment ID, period start, period end, days, rate basis, price, amount |
| Progress claim | One claim/detail occurrence | Contract amount, claim round, previous, current, cumulative and remaining amounts |
| Supplier ledger | One ledger event | Transaction date, event type, net amount, tax, payment, balance |

For example, a fictional source row `품명=Panel; 면적=4.5; 수량=6;
단위=EA; 단가=100; 금액=600` becomes separate work-area and billed-quantity
columns because the source expresses different quantity roles. A rental record
does not justify using that area-based layout or assuming days × monthly rate.
Similarly, a ledger's opening balance and payment are not new purchased items.
Display views may emphasize the user's purpose after these meanings are preserved.

## Document-type-specific headers

Keep trade classification at major (trade), middle (activity), and minor
(specific operation). Design business headers independently from that hierarchy.
Share document identity, party roles, project/date metadata and provenance only
where their meanings agree. Give each observed document type its own ordered
detail headers and row meaning; compatible types may share a detail table when
their semantics agree. Do not create a universal flat table or a new table for
every filename merely to separate layouts.

Use the following as conditional examples, not required columns or evidence:

| Document type | Detail grain | Candidate detail headers, only with source support |
|---|---|---|
| Purchase order | One ordered item occurrence | Item, specification, ordered quantity/unit, unit price, ordered amount, requested delivery date |
| Transaction statement | One supplied/billed item occurrence | Item, specification, supply date, delivered quantity/unit, billed quantity/unit, unit price, supply amount |
| Progress claim | One claim item per round | Claim round, contract amount, previous amount, current amount, cumulative amount, remaining amount |
| Labour record | One worker/work-date occurrence | Work date, worker identifier as stated, operation, attendance/work units, hours, rate basis, rate, amount |
| Equipment rental | One equipment/usage occurrence | Equipment identifier, rental start/end, usage quantity/unit, rate basis, rate, amount |

Split a source description into separate fields when each has an independent
meaning useful for retrieval, calculation or validation and the source wording,
layout or explicit units establish that meaning. For example, an explicit
`3층 알루미늄 패널 설치` can support floor=3층, material=알루미늄,
item=패널, operation=설치; retain the complete original description and locate
each interpretation. `패널 설치` supplies no floor or material. A supplier's
name, folder label, industry convention or common product composition cannot
supply those missing values. Ambiguous tokens stay in the original text with
an issue rather than being forced into a field.

For each added/subdivided field, record its meaning, type/unit, supporting source
label/text and location, extraction/normalization rule, and missing-value rule
in the existing field dictionary and mapping. Create source-based detail fields
only when observed content supports them; do not add speculative columns from
the examples. A field evidenced elsewhere in the reviewed scope may be null on
rows where absent. Keep original, normalized and derived values distinguishable;
any derived value needs its own stated rule and input references and cannot
masquerade as a source-observed attribute. Retain distinct date, quantity and
amount roles even when values happen to agree, especially previous/current/
cumulative amounts. Review new fields or meanings as contract changes before
conversion; do not silently modify an existing database schema.

## Handoff and completion boundary

Record model evidence, grain, relationships, ordered headers, database fields,
source mappings, actual rows, coverage review and the model decision in
`structure.md`. Include the user's purpose where known. Identify the primary
business table for requested conversion and retain supporting provenance.

Do not deliver `cells_json`, text-line lists, or a file inventory as the user's
final business table. If a source cannot be interpreted, preserve its raw evidence
and report an explicit incomplete item; continue processing other readable files.
Scope limitations are findings, not a reason to silently replace the requested
transformation with raw extraction. The existing starter ERD is illustrative:
adapt it to the observed data and requested purpose.
