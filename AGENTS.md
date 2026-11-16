# Axis Migration

Read `output/agents.md` before processing an input folder. Inspect its structure
before designing tables or converting records. Use the two skills in
this package: `construction-schema-design`, then `construction-data-migration`.

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
