# Changelog

## Unreleased

- Give each Codex stage a read-only `scripts/axis_tools.py` MCP server bound to
  its run, with `verify_db` applying the final checks before the stage reports
  ready. The runner still repeats the verification and owns run control.

- Publish the reusable WebGL relationship renderer and component styles:
  matte round points, edge-driven 3D layout, orbit/pan/zoom, source selection,
  keyboard/reduced-motion support and SVG fallback. Document the host contract;
  keep private graph data, integrated company viewers and databases external.

- Persist private run states and result paths with `scripts/run_status.py`;
  read them back for completion, decision/input waiting, and error notices.
  Share this workflow across the three skills without changing business DBs.

- Add a read-only dashboard with grouped Korean table names, row counts,
  explanation search, table grain/interpretation/cautions, and related links.
- Add per-table Korean column labels, field meanings, unit evidence and
  uncertainty guides, retaining original database and CSV/SQL field names.
- Load company table/column descriptions from an external `--catalog` JSON file;
  document the workflow and verification in `docs/2026-11-17.md`.
- Start/resume a private `.axis_migration/record.md` in the selected input folder,
  preserving append-only progress, user decisions and result locations across skills.
- Add counterparty-first trade/activity/operation classification proposals,
  a configurable starter table, and source-text mapping before classification.
- Add `construction-document-matching`: supply-chain role mapping, evidence-ranked
  order/statement links, quantity and amount reconciliation with rounding
  detection, party identity review and open (unbilled) items.
- Add `scripts/reconcile.py`: exact-decimal line, total, tax and written-amount
  checks, truncation-pattern detection, cumulative checks and open items.
- Align both skills and package guidance around document-based model proposals,
  full requested-scope coverage review, then defined-model conversion.
- Require located model evidence, coverage statuses, model version/decision
  basis and evidence-backed target field/function comparisons.
- Separate source reading, semantic mapping, source conflicts, arithmetic and
  database findings while preserving original-source and quantity rules.

## 0.1.0

- Make user intent, proposed headers, and actual rearranged sample rows the
  starting point for document migration, including PDF and image interpretation.
- Require mapped business columns as the final result; raw evidence is intermediate.
- Open and verify the primary business table rather than the raw extraction table.

- Two construction schema and migration skills.
- Read-only local SQLite table viewer with CSV and SQL exports.
- Explicit stable-tag updates, installation backup, and rollback.
- Preserve local configuration and generated outputs during version changes.

- Define folder → purpose → headers → accumulation → migration as the product goal.
- Document incremental ingestion as agent guidance and an upcoming engine milestone.
