# Construction matching checks

| Situation | Preserve or verify | Cause → remedy when unresolved |
|---|---|---|
| Statement supplier is not the order addressee | Party chain from the delivery block or remarks | Role unclear → keep the line `unmatched_statement_line` and ask for the routing |
| Fabricator and finisher bill the same quantity | Each link's item and work type | Different work → two valid links; same work → `overbilled` review |
| Statement cites a round but quantities differ | Both quantities and the cited round | Partial delivery or revision → check delivery notes before linking fully |
| Piece count matches but area differs | Each measure separately | Measure basis differs → confirm which measure is billed |
| Area billed while order lists pieces | Order area field or drawing evidence | No area on order → `not_checkable`; request the area basis |
| One statement covers several rounds | One link per round | Lines merged → split only with printed per-round evidence |
| One round billed over several statements | Partial links summed per round | Sum exceeds order → `overbilled` |
| Every line amount ends below a common unit | Source amount and calculated amount | Rounding rule → `amount_truncated`, confirm with counterparty |
| Order cover and detail sheets disagree on spec | Both values and locations | Template carry-over or real change → `spec_conflict`, confirm delivery |
| Cumulative field disagrees with rounds | Per-round quantities | Register error → `cumulative_inconsistency` |
| Representative or address differs from order contacts | All identity fields | Contact person ≠ registered owner → `party_identity_review` |
| Urgent small round not on the latest statement | Order date versus statement cut-off | Later billing → `unbilled`, keep open |
| Equal totals on unrelated documents | Nothing beyond the coincidence | Amount alone → no link |

## Boundaries

Do not approve or schedule payment, infer progress percentages, enforce
contract tolerances that were not supplied, or compare prices across companies
without a supplied basis. Those need a separately requested workflow.
