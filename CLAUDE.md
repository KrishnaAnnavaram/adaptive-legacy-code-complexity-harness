# adaptive-legacy-code-complexity-harness

Measures the complexity of legacy code from a **parse tree** and consolidates the
result into one artifact. Producing the tree is upstream and out of scope here.

## Pipeline

```
Java repo ──1_inventory──► inventory_artifact.json ──2_parser──► Normalized Tree ──3_complexity──► complexity_artifact.json
```

## Commands

```bash
# scan a Java repo
python .claude/inventory/scanner.py --repo-root <path> -o out

# run all 20 complexities over a tree
python .claude/complexities/run_pipeline.py samples/cobol_payroll.tree.json -o out

# one complexity, standalone or piped
python .claude/complexities/17_runtime_complexity.py tree.json
cat tree.json | python .claude/complexities/01_cyclomatic_complexity.py

# list what is installed and what each needs
python .claude/complexities/run_pipeline.py --list

# audit the analyzers themselves — ALWAYS run before opening a PR
python tools/judge.py samples/cobol_payroll.tree.json --self-test
```

Expected: `measured 20/20 (100%)` and `20 pass 0 CRITICAL` with the canary flagged.

## Layout

| Path | What it holds |
|---|---|
| `.claude/agents/` | Agent definitions — the orchestrators |
| `.claude/skills/` | 20 skills: **what** each complexity is and **when** to use it |
| `.claude/complexities/` | **Product code.** The 20 implementations + `_core.py` + pipeline |
| `.claude/inventory/` | **Product code.** Java repo scanner |
| `docs/` | Contracts and architecture decisions |
| `tools/` | Judge, canary, legacy tree bridge |

> `.claude/complexities/` and `.claude/inventory/` are the **deliverable**, not
> editor configuration. Do not delete `.claude/` assuming it is tooling.

## The rule everything rests on

**An analyzer starved of its declared inputs returns `insufficient_input` naming
the gap. It never returns a zero.**

Absence of measurement and absence of complexity are different facts. Collapsing
them produces a clean-looking report built on nothing. This is enforced centrally
in `_core.run()` before any analyzer is invoked — do not bypass or reimplement it.

## Conventions

- **Standard library only** in `.claude/complexities/` and `.claude/inventory/`.
  Clients are frequently air-gapped where installing a package takes weeks.
- **Deterministic output.** Same tree in, same bytes out. No timestamps inside an
  analyzer's report; the pipeline stamps the run once.
- **Analyzers are pure functions.** `analyze(tree) -> dict`. No file IO, no
  globals, no printing. The CLI is a thin shell around it, never the reverse.
- **`skills/` describes, `complexities/` implements.** One pairs with the other by
  number: `skills/runtime-complexity/` ↔ `complexities/17_runtime_complexity.py`.
- **Never write to stdout from an analyzer** except the final JSON. Diagnostics go
  to stderr — a stray `print()` corrupts the report.

## Adding complexity #21

Copy an existing `NN_*.py`, edit its `SPEC`, write `analyze()`, add
`.claude/skills/<name>/SKILL.md`. Nothing else changes — the agent and pipeline
discover it by scanning. Contract: @docs/analyzer-contract.md

## Never commit

`plsql_to_brd/` is a **separate repository** that sits inside this working
directory and carries its own `.git`. It is in `.gitignore` and must stay there.
Committing it produces a broken submodule reference or absorbs its history —
neither is cleanly recoverable once pushed.

## Before opening a PR

1. `python .claude/complexities/run_pipeline.py samples/cobol_payroll.tree.json -o out`
2. `python tools/judge.py samples/cobol_payroll.tree.json --self-test`
3. Confirm `git status` shows no `plsql_to_brd/`, no `out/`

There is no CI. These checks are manual and are the only thing standing between a
defect and `main`.
