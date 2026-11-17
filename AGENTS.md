# Axis Migration

Read `output/agents.md` before processing an input folder. Use
`construction-schema-design` to inspect file contents, propose an industry- and
company-appropriate data model with evidence, then review whether the model can
represent the full requested source scope. Once the model is defined, use
`construction-data-migration` for requested conversion and integrity checks,
then `construction-document-matching` when order/statement matching is requested.
Design-only requests stop at the model and coverage review; a supplied model
can be reused after checking its fit. Do not require a business purpose merely
to discover the source structure, or treat a representative sample as full coverage.

When an input directory is selected, read/create its private
`.axis_migration/record.md`, append the start entry, and keep decisions/progress
and result links there. Read it first on later invocations. Exclude this record
directory from document discovery; reports and exports retain their separate
run locations. Keep all company records outside this public package.

The user's explicit input directory determines the output location. Never use
the agent's current working directory as an implicit substitute for that input.
This package's `output/` contains instructions, not private business data.

Keep company mappings and generated business records outside this package.
Reuse the original-source, quantity, provenance, and validation rules in the
skills. Company classifications are optional supplied mappings.

For a requested local migration, create and validate a fresh SQLite database
in the designated run directory. This is authorized local output generation;
it does not authorize writing to an existing production database.
Use `scripts/view_db.py` to show the resulting tables on loopback only.
The local page and database require no hosted services. If the agent itself
uses a remote model, that is not a guarantee of fully offline document inference.

## Requested updates

When asked to update Axis Migration, read the README version-update workflow.
Run `scripts/update.py check` before `update`, report the selected stable tag,
stop active migration/viewer work, then apply the requested update. Use the
configured repository or the user's explicit repository. Never invent its URL.
Do not modify existing database schemas as part of a package update. Explain
how to restart the session and restore the printed backup if needed.
