# Matching contract

## Inputs

Require the reference company, the matching scope, and source records with
document identity, line identity, source location and contract version. Records
from `construction-data-migration` satisfy this. Supplied unit-price lists,
contracts or quotations are optional and recorded with their version.

## Output tables

Keep links and findings separate from the source business tables. Never rewrite
source rows to make them agree.

### `match_links` — one row per evidenced link

| Field | Meaning |
|---|---|
| `link_id` | Stable ID derived from the linked source IDs |
| `order_document_id`, `order_round` | Order side; round or line as printed |
| `statement_document_id`, `statement_line_id` | Statement side |
| `link_type` | `same_goods`, `service_on_ordered_goods`, `partial_delivery`, `multi_round_statement` |
| `order_count`, `statement_count` | Piece counts as printed |
| `order_measure`, `statement_measure`, `measure_unit` | Area/length/weight as printed, with unit |
| `evidence` | Located reasons: reference text, quantity identity, chain role |
| `status` | See statuses below |
| `contract_version` | Matching contract and price-basis version used |

### `match_findings` — one row per finding

| Field | Meaning |
|---|---|
| `finding_id`, `link_id` | `link_id` is null for document-level findings |
| `document_id`, `source_location` | Where the finding is evidenced |
| `code` | See finding codes below |
| `source_value`, `compared_value`, `difference` | Exact decimals as text |
| `cause`, `remedy` | Plain explanation and concrete next step |

### `open_items` — derived per order round

Ordered quantity, linked quantity, remaining quantity and status. Recompute it
from `match_links` on every run; do not store it as a source fact.

## Statuses

| Applies to | Status | Meaning |
|---|---|---|
| Order round | `matched` | Linked quantity equals ordered quantity at displayed precision |
| Order round | `partially_billed` | Linked quantity is less than ordered |
| Order round | `unbilled` | No link yet; an open item |
| Order round | `overbilled` | Linked quantity exceeds ordered |
| Either side | `ambiguous` | More than one candidate fits equally; resolving evidence named |
| Statement line | `unmatched_statement_line` | No order round in the chain supports it |

## Finding codes

| Code | Raised when | Typical remedy |
|---|---|---|
| `rounding_difference` | Values differ only within the shown precision | None; record both values |
| `amount_truncated` | Each line's amount drops the same trailing unit | Confirm the counterparty's rounding rule |
| `amount_difference` | Line amount differs beyond a consistent rounding pattern | Ask for a corrected statement |
| `quantity_mismatch` | Counts or measures differ beyond rounding | Check delivery records and the order revision |
| `unit_price_not_checkable` | No contract, quotation or prior price supplied | Supply the price basis |
| `unit_price_difference` | Price differs from the supplied basis | Confirm the agreed price |
| `party_identity_review` | Registration, name, representative, address or contact differ | Compare with the tax invoice or registry record |
| `cumulative_inconsistency` | Order cumulative field ≠ sum of rounds | Use per-round quantities; correct the order register |
| `spec_conflict` | One source gives two specifications | Confirm with the supplier's delivery or mill record |
| `date_order_conflict` | Statement predates the order | Check for a pre-order or misdated document |
| `reference_missing` | Statement names no order or round | Ask the counterparty to cite the order |
| `total_difference` | Supply ≠ line sum, or total ≠ supply + tax | Ask for a corrected statement |
| `tax_difference` | Tax differs from supply × a stated rate | Confirm the tax basis |
| `written_amount_difference` | Written amount ≠ numeric total | Confirm which amount is intended |
| `amount_not_checkable` | A line has an amount but no quantity or price | Obtain the pricing basis |
| `unbilled_round` | An order round has no link at the cut-off date | Track as open; no correction needed |

Use `not_checked` or `not_checkable` with a reason rather than a pass when the
evidence is missing.

## Fictional worked example

All parties and values are synthetic.

Example Contractor sends panel orders to Example Fabricator. Each order's
delivery block routes goods Example Fabricator → Example Insulation → site,
with a remark that insulation is installed on the panel backs.

| Order round | Pieces | Area (m²) |
|---|---|---|
| R2 | 40 | 52.36549 |
| R3 | 90 | 118.20410 |
| R4 | 2 | 1.10230 |

Example Insulation's statement:

| Line | Item | Area (m²) | Unit price | Amount |
|---|---|---|---|---|
| 1 | Insulation, R2 – 40 pcs | 52.37 | 7,300 | 382,300 |
| 2 | Insulation, R3 – 90 pcs | 118.20 | 7,300 | 862,800 |

Supply 1,245,100; tax 124,510; total 1,369,610.

Result:

- Lines 1 and 2 link to R2 and R3 as `service_on_ordered_goods`. Evidence: the
  supplier is in the delivery chain, the line cites the round, and piece counts
  and areas agree at two decimals.
- 52.37 × 7,300 = 382,301 and 118.20 × 7,300 = 862,860. Both lines drop the
  amount below 100, so record `amount_truncated` (−1 and −60).
- Supply, 10% tax line and total agree.
- No price list was supplied: `unit_price_not_checkable`.
- R4 has no link: `unbilled`, listed in `open_items`.
