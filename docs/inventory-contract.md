# What the inventory agent promises: `inventory_artifact.json`

This is the interface between `0_inventory_agent` and whatever parser agent
reads its output next. It is a schema doc, not code — nothing executes this
file. Its only job is to let the parser agent be written against a fixed
contract instead of `scanner.py`'s source.

Produced by [`.claude/inventory/scanner.py`](../.claude/inventory/scanner.py).
Read the agent's operating rules in
[`0_inventory_agent.md`](../.claude/agents/0_inventory_agent.md).

---

## What this is, and what it deliberately is not

The inventory agent reads **file structure and declarations** — package
names, type names, imports, `extends`/`implements` clauses. It is regex-based
on purpose: fast, dependency-free, good enough to tell a parser *what exists
and where*.

It does **not** read method bodies, resolve overloads, build a symbol table,
or produce a control-flow graph. Any field you'd expect from a real Java
parser (call graphs, CFGs, variable references) is out of scope here — that's
the next agent's job, and it should not expect this artifact to have it.

Consequence: resolution in this artifact is **best-effort**. Two classes with
the same simple name in different packages, or a class referenced only via a
wildcard import, may resolve incorrectly or not at all. Every place this can
happen is called out below. Nothing here should be trusted as ground truth the
way a real parser's output would be — treat `resolved: true` as "probably
right, cheap to compute," not as a guarantee.

---

## Top-level shape

```jsonc
{
  "meta": { ... },
  "stats": { ... },
  "file_registry": [ ... ],
  "build_registry": [ ... ],
  "config_registry": [ ... ],
  "sql_registry": [ ... ],
  "dependency_graph": { "nodes": [ ... ], "edges": [ ... ] },
  "issues": [ ... ]
}
```

### `meta`

| Field | Type | Notes |
|---|---|---|
| `generated_at` | string | UTC timestamp, `YYYY-MM-DDTHH:MM:SSZ` |
| `repo_root` | string | Absolute path scanned |
| `language` | string | Always `"java"` |
| `agent_version` | string | e.g. `"0_inventory_java@1.0"` |
| `total_files_scanned` | number | Every file matched by extension, including build/config/sql |

### `stats`

Aggregate counts only — every number here is derived from `file_registry` /
`dependency_graph` and exists for a quick "did this run look sane" check, not
as a separate source of truth. See `scanner.py::compute_stats` if a count
looks wrong; it is always recomputable from the arrays below it.

### `file_registry`

**One entry per top-level type declaration — not one per file.** A single
`.java` file with a public class and a package-private helper class produces
two entries sharing the same `path`. Nested/inner classes are **not**
registered separately; they're invisible to this artifact (the parser will
see them when it actually parses the file).

| Field | Type | Notes |
|---|---|---|
| `id` | string | `package.TypeName`, or bare `TypeName` if no package. **This is the join key** — the parser agent should use this as the unit id it carries forward. |
| `name` | string | Simple type name |
| `package` | string | May be `""` |
| `kind` | `"class" \| "interface" \| "enum" \| "record" \| "annotation"` | |
| `is_public` | boolean | |
| `path` / `relative_path` | string | Repo-relative, forward slashes. Multiple entries can share this. |
| `line` | number | Line the type keyword appears on |
| `loc` | number | Line count of the **whole file**, not just this type — if a file declares two types, both entries carry the same `loc` |
| `size_bytes` | number | Whole-file size |

### `build_registry` / `config_registry` / `sql_registry`

Flat lists of `{ path, relative_path, type }`. `build` = `pom.xml` /
`build.gradle(.kts)` / `settings.gradle(.kts)`; `config` = `.xml` / `.properties`
/ `.yml` / `.yaml` that isn't a build file; `sql` = `.sql`. Not parsed —
presence and location only. If the parser needs dependency versions out of
`pom.xml`, it reads the file itself; this artifact only tells it the file
exists.

### `dependency_graph`

`nodes`: one per `file_registry` entry, `{ id, kind, path }` — a thin
projection, safe to rebuild from `file_registry` alone if convenient.

`edges`: `{ from, to, type, resolved, source_line_hint, ...extra }`

| `type` | Meaning | `to` when `resolved: true` | `to` when `resolved: false` |
|---|---|---|---|
| `IMPORT` | an `import` statement | target `id` in `file_registry` | the raw import string (may end `.*` for a wildcard) |
| `IMPORT_STATIC` | `import static ...` | same as above | same as above |
| `EXTENDS` | a class/interface's `extends` clause | target `id` | the raw token as written in source (simple name, generics stripped) |
| `IMPLEMENTS` | an `implements` clause | target `id` | same as above |

**`resolved: false` is the expected, common case for `IMPORT`** — most
imports are JDK or third-party classes this repo doesn't declare, so they
can't resolve to a `file_registry` id. It is not a defect and not something to
flag. For `EXTENDS`/`IMPLEMENTS` it usually means the supertype is external
(e.g. `extends RuntimeException`), which is equally normal.

**Resolution order for `EXTENDS`/`IMPLEMENTS`** (best-effort, in this
priority): (1) already dotted → looked up as-is; (2) matches a simple name
this file explicitly imports → that import's target; (3) matches a type in
the same package; (4) matches exactly one same-named type anywhere else in the
repo (ambiguous if more than one — falls through to unresolved). Generic
parameters are stripped before matching (`Comparable<Foo>` → `Comparable`).

### `issues`

`{ severity: "info"|"warning"|"error", type, message, ...context }`. Unlike
unresolved edges, every issue here is worth a human or the parser agent
looking at:

| `type` | Severity | Means |
|---|---|---|
| `empty_repository` | error | Zero `.java` files found anywhere under `repo_root` — scan aborted, all other arrays empty |
| `file_read_error` | error | A file couldn't be read (permissions/encoding) |
| `duplicate_type_id` | error | Two files declare the same `package.TypeName` — a real problem, not a resolver artifact |
| `no_type_declaration` | warning | A `.java` file had no discoverable top-level type; it is **not** in `file_registry` at all |
| `public_type_filename_mismatch` | warning | The public type's name doesn't match its filename (won't compile as-is; likely a copied/generated file) |
| `possible_inheritance_cycle` | warning | Two types appear to extend/implement each other. Valid Java can't compile a real cycle, so this almost always means the same-name resolver (step 4 above) picked the wrong class — verify manually before trusting the edge |
| `unclassified_extension` | info | A file didn't match any known extension; skipped, not scanned |

---

## Worked example

No fixture ships in this repo yet — point `--repo-root` at any small Java
project to see the shape in action:

```bash
python .claude/inventory/scanner.py --repo-root /path/to/a/java/repo -o out
```

A repo with a package-local `implements` (e.g. `Circle implements Shape`,
both in the same package), a same-package `extends`, and a couple of JDK
imports (`java.util.List`, `implements Runnable`) is enough to exercise every
edge type in the table above: two resolved edges (`IMPLEMENTS`, `EXTENDS`)
and two unresolved ones (`IMPORT`, `IMPLEMENTS` against `Runnable`).

---

## Known limits (read before building the parser against this)

- **No nested/inner/local/anonymous classes.** Only top-level types are
  registered. If the parser needs those, it discovers them itself when it
  actually opens the file.
- **One `extends` target assumed for classes; `extends` can be a list for
  interfaces** (an interface may extend several). The field is always a list
  regardless, so this doesn't change the shape — just don't assume length 1.
- **Same-simple-name ambiguity.** If two unrelated types share a name and
  neither is imported nor same-package, resolution silently gives up
  (`resolved: false`) rather than guessing — but if exactly one same-named
  type exists elsewhere in the repo, step 4 above *will* guess, and it can be
  wrong for large repos with common names like `Result` or `Config`.
- **Comments/strings are blanked, not removed**, so line numbers stay accurate
  — but a `class`/`extends`/etc. keyword inside a text block or annotation
  argument that survives blanking (rare) could theoretically produce a false
  match. Not observed in testing; noted for completeness.