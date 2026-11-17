# Construction migration checks

This is the conversion checklist. Schema discovery and broader interpretation
belong to the schema-design skill; an export must follow its explicit contract.

| Situation | Preserve or verify | Cause → remedy when unresolved |
|---|---|---|
| Supplier and buyer appear together | Each party's labelled role | Party role unclear → retain raw labels and request the missing context |
| Area plus piece/metre/kg pricing | Work area and billed quantity/unit separately | Pricing basis ambiguous → keep source quantities and flag the billed basis |
| No source work area | Null work area; optional derived area separately | Area absent → obtain source evidence instead of substituting piece count |
| Amount-only charge | Amount with null quantity and price | Arithmetic basis missing → mark not checkable, preserve the charge |
| Source and calculated amount differ | Both values and source-minus-calculated difference | Calculation disagrees → inspect the original and applicable rounding rule |
| Tax or discount on a separate line | Its role and evidence | Tax basis or adjustment unclear → report it without assuming a rate or balancing row |
| Repeated headers, subtotals, carry-forwards | Row roles and correct aggregation scope | Summary counted twice → exclude it from detail sums, retain its source record |
| Repeated identical detail rows | Distinct source occurrences and line IDs | Duplication uncertain → flag, do not delete on item/amount equality alone |
| Same file or repeated page copy | File/page identity and demonstrated duplicate occurrence | Copy identity unclear → retain review evidence before collapsing an occurrence |
| Multiple files form one statement | Document identity, logical order, and all physical locations | Continuation uncertain → keep separate candidates, request identifying evidence |
| Merged project/date cells | Bounded inheritance and original blank cells | Group boundary unclear → retain null and identify the boundary needing review |
| New field or a changed unit | Raw value and proposed contract revision | Target lacks a field → preserve in raw data/review output and revise explicitly |
| Missing company master/category map | Source names/categories; normalized fields null | Company mapping unavailable → accept raw extraction and defer normalization |
| Dates outside a filename's month | Original dates/year | Filename conflicts with contents → report the conflict without changing dates |

## Continuation evidence

Connect pages when the user identifies the continuation or the document
number/page sequence and content give an unambiguous connection without
conflicting evidence. Record who/what established it. A suffix such as `~1`,
similar site names, or a matching difference alone is not enough.

After connecting, record logical page order and physical file/page locations,
trace inherited header values to their source, count demonstrated repeated
page copies once, and recheck the whole document. Preserve other unresolved
issues even if a previously missing page explains the total difference.

## Boundaries

Do not match an order to a statement as part of this export; that belongs to
`construction-document-matching` when requested. Inferring progress/payment
status, enforcing process-yield limits, or comparing prices across companies
need explicit business rules and a separate requested workflow.
