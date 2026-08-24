# Target language descriptor schema

One JSON file per target language, under `languages/` (live, trusted) or
`languages/_pending/` (drafted, not yet trusted — see that folder's README).
The file's own name is the language id `target_fit.py` looks up: `python.json`
answers `--target python`.

The analyzer never hardcodes a language name anywhere in its own code — every
field it reads comes from this file. Adding a new target is writing one of
these, never touching `target_fit.py`.

## Required fields

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Must match the filename stem. |
| `display_name` | string | Human-readable name used in generated prose. |
| `structured_control_flow_only` | bool | `false` if the language allows unrestricted jumps (e.g. COBOL `GOTO`/`PERFORM THRU`). |
| `supports_goto` | bool | Literal `GOTO`-equivalent exists. |
| `supports_alter_style_dynamic_jump` | bool | A jump target can be rewritten at runtime (COBOL `ALTER`). Almost always `false` outside COBOL. |
| `typing` | `"static"` \| `"dynamic"` | |
| `numeric_model.native_fixed_point` | bool | Does the language have a *native* exact fixed-point/decimal type, not a library bolt-on. |
| `exception_model` | string | One line: how errors propagate (exceptions, return codes, status fields, ...). |
| `native_sql_access` | string | How SQL is reached: embedded, driver/DB-API, ORM-first, none. |
| `native_screen_io` | bool | Does the language itself talk to a screen, or does that require an external framework. |
| `source` | `"drafted"` \| `"reviewed"` | Provenance marker. |
| `reviewed` | bool | Has a human checked this file's fields against real documentation. Findings derived from an unreviewed descriptor carry reduced confidence — see `docs/target-fit-contract.md`. |

## Optional fields (lower confidence, not a blocker, if absent)

`garbage_collected`, `manual_memory_management`, `concurrency_model`,
`multiple_inheritance`, `multiple_inheritance_notes`, `notes`.

## Adding a new target

1. Copy an existing file in `languages/` as a starting point.
2. Fill in every required field for the new language — from real
   documentation, not impression.
3. Set `"source": "drafted"`, `"reviewed": false`, save it to
   `languages/_pending/<id>.json`.
4. Have someone check it, then move it into `languages/` and flip
   `"reviewed"` to `true`.

Nothing else changes. `target_fit.py` discovers it by filename the next time
that target is requested.
