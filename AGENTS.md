# Axis Migration

Use the Axis Migration MCP server as the default entry point for a requested
local folder migration when it is available. Call `start_folder` with the
explicit input path, or `resume_folder` with a saved run path, then follow
`folder_status` and share the local review or result URL. The runner asks Codex
to read the workflow instructions and load each bundled skill at its stage.
Use the direct runner when MCP is unavailable or the user requests the CLI.

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

For design, conversion, matching and viewer tasks, follow
`construction-schema-design/references/run-status.md`. Use `scripts/run_status.py`
to save the actual stage/state and result paths in private `status.json`, then
read it before the final notice. Distinguish completion, waiting for a decision
or input, and execution errors. Never infer completion from raw extraction,
an old successful run, or a still-running viewer.

## Requested updates

When asked to update Axis Migration, read the README version-update workflow.
Run `scripts/update.py check` before `update`, report the selected stable tag,
stop active migration/viewer work, then apply the requested update. Use the
configured repository or the user's explicit repository. Never invent its URL.
Do not modify existing database schemas as part of a package update. Explain
how to restart the session and restore the printed backup if needed.
