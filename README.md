# adaptive-legacy-code-complexity-harness

Adaptive, language-aware harness for identifying legacy source code, selecting applicable
complexity analyses, orchestrating execution, generating traceable metric-level reports,
and consolidating results into a unified code complexity artifact.

**Input:** a parse tree — ANTLR, AST, or an upstream parser artifact.
**Output:** one unified complexity artifact.
**Shape:** one agent, twenty skills, one contract.

---

## Layout

```
.claude/
  agents/
    0_inventory_agent.md            scans a Java repo -> inventory_artifact.json
    1_complexity_agent.md           the complexity orchestrating agent
  inventory/scanner.py              deterministic Java repo scanner (no skills — one job)
  skills/<complexity>/SKILL.md      20 skills, one per complexity — what & why
  complexities/
    _core.py                        the shared contract
    01_..20_*.py                    deterministic implementation per skill
    run_pipeline.py                 discover → order → gate → run → merge
    _superseded_style_a/            Style-A originals, preserved
docs/
  system-overview.md                start here
  inventory-contract.md             schema of inventory_artifact.json
  analyzer-contract.md              how to build a complexity
  architecture-decisions.md         why it is built this way
samples/cobol_payroll.tree.json     reference tree, exercises every field
tools/
  judge.py                          adversarial conformance audit
  99_canary_complexity.py           defective on purpose; validates the judge
  tree_bridge.py                    converts legacy Style-A trees
```

Pipeline: `0_inventory` scans a Java repo and emits `inventory_artifact.json`
(schema: [`docs/inventory-contract.md`](docs/inventory-contract.md)) → an
upstream parser agent (ANTLR/AST, owned separately) turns that into a
Normalized Tree → `1_complexity` scores it. Inventory has no `skills/`
directory: it is one deterministic scan, not twenty selectable analyses, so
there is nothing to discover or choose among at runtime.

```bash
python .claude/inventory/scanner.py --repo-root <path-to-java-repo> -o out
```

**`skills/` describes, `complexities/` implements.** A `SKILL.md` states what the
complexity measures, which tree fields it consumes, what it emits and how it fails; the
matching `NN_*.py` is the deterministic implementation. Both are generated from the same
source, so they cannot drift apart.

---

## The twenty complexities

Every one is language-agnostic — they read a tree, never source text, so the same script
scores COBOL, PL/SQL and Java.

| Band | # | Complexity | Measures |
|---|---|---|---|
| size | 07 | Structural | Size and its distribution — where the mass sits |
| structural | 01 | Cyclomatic | Independent paths; the floor on test cases |
| | 02 | Cognitive | Readability cost; penalises nesting |
| | 03 | Control Flow | Unstructuredness; whether translation is viable |
| | 05 | Nesting | Control-structure depth |
| | 06 | NPath | Acyclic paths; what branch coverage misses |
| | 17 | Runtime | Growth class O(1)…O(2ⁿ) from loop nesting |
| data | 12 | Data Flow | How values and shared state move |
| coupling | 04 | Coupling | Fan-in/out; what can be extracted |
| | 08 | Cohesion | Whether a type's members belong together |
| | 09 | Dependency | Weight and kind of module dependencies |
| | 10 | Change Impact | Blast radius of a change |
| | 13 | Inheritance | Hierarchy depth and width |
| | 14 | Interface / API | Exposed contract surface |
| | 20 | Architectural | Cycles, Martin zones, layering, hubs |
| hazard | 15 | Database | SQL surface, dynamic SQL, N+1 patterns |
| | 18 | Configuration | External surface, build variants, hardcoding |
| composite | 11 | Maintainability | Maintainability Index |
| | 16 | Testability | Test burden vs test friction |
| | 19 | Migration | Volume vs blockers → migration strategy |

---

## Run it

```bash
# all twenty
python .claude/complexities/run_pipeline.py samples/cobol_payroll.tree.json -o out

# one skill, standalone or piped
python .claude/complexities/17_runtime_complexity.py tree.json
cat tree.json | python .claude/complexities/01_cyclomatic_complexity.py

# what is installed and what each needs
python .claude/complexities/run_pipeline.py --list
```

Embedded in any harness:

```python
from importlib import import_module
report = import_module("17_runtime_complexity").analyze(tree)
```

Reference run:

```
measured 20/20 (100%)   not measured: 0   errors: 0
overall level L5   hotspots 3
```

---

## The rule everything rests on

**A skill starved of its declared inputs returns `insufficient_input` naming the gap.
It never returns a zero.**

This is not a style preference. Analyzers here once returned clean-looking zeros — and
one batch printed complete reports built from hardcoded sample data — when handed input
they could not read. Verified: given a file declaring `language: ZZZ-MY-FILE` with 1
unit, one analyzer reported `language: java` with 2 units. Running the suite would have
produced 7 genuine results and 13 fabricated ones, with nothing distinguishing them.

Zeros look like good news. The gate is enforced centrally in `_core.run()` before a skill
is ever invoked, so it cannot be forgotten by an individual author.

---

## Audited, not asserted

```bash
python tools/judge.py samples/cobol_payroll.tree.json --self-test
# 20 pass   0 minor   0 CRITICAL
# self-test OK: canary correctly flagged CRITICAL
```

Ten adversarial checks per skill: contract conformance, starvation behaviour,
determinism, evidence behind severe scores, honest input declaration.

`C10` is the one that matters. `C2` can only exercise the central gate, so it proves a
SPEC is *wired*, not *complete*. `C10` strips undeclared inputs and fails a skill whose
score moves while confidence stays at 1.0. It caught two real defects on its first run —
skills #18 and #19 both read line counts they never declared, and #18 treated an unknown
line count as maximal scatter, manufacturing a finding out of missing data.

`tools/99_canary_complexity.py` is defective on purpose and **must** come back CRITICAL.
The judge passed all 20 skills on its first run, which is equally consistent with a judge
that cannot detect anything — the canary is how you tell the difference.

---

## Add complexity #21

```bash
cp .claude/complexities/01_cyclomatic_complexity.py .claude/complexities/21_my_complexity.py
mkdir .claude/skills/my-complexity
```

Edit the `SPEC`, write `analyze()`, add the `SKILL.md`. Nothing else changes — the agent
and pipeline discover it by scanning. Full contract in
[docs/analyzer-contract.md](docs/analyzer-contract.md).

---

## Known limits

- **Band calibration is judgement, not measurement.** Thresholds reflect published
  practice and field experience, not a statistical study of a reference corpus. Re-fit
  them against your own codebase once enough runs exist.
- **A tree is only as good as its parser.** Skills report what the tree carries. If the
  parser drops comments, data references or a control-flow graph, the affected skills say
  `insufficient_input` — which is a parser gap, not a clean codebase.
- **`_superseded_style_a/`** holds the original Style-A analyzers, preserved unmodified.
  `tools/tree_bridge.py` converts a Style-A tree if you still have one.
