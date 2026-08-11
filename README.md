# adaptive-legacy-code-complexity-harness

Adaptive, language-aware harness for identifying legacy source code, selecting applicable
complexity analyses, orchestrating execution, generating traceable metric-level reports,
and consolidating results into a unified code complexity artifact.

**Input:** a parse tree — ANTLR, AST, or an upstream parser artifact.
**Output:** one unified complexity artifact.
**Shape:** one agent, twenty skills, one contract.

---

# Architecture

## Data flow

Three stages, each owning one job and handing off a documented artifact. Nothing
downstream ever re-reads source code.

```
  Java repo
      │
      ▼
┌─────────────────┐   agent: java-inventory
│  0. INVENTORY   │   .claude/inventory/scanner.py
└─────────────────┘   regex/heuristic. Declarations only — never enters a method body.
      │
      ▼  inventory_artifact.json            schema: docs/inventory-contract.md
      │
┌─────────────────┐   ── OWNED SEPARATELY, NOT IN THIS REPO ──
│  1. PARSER      │   ANTLR / AST producer. Builds the Normalized Tree.
└─────────────────┘
      │
      ▼  Normalized Tree (JSON)             schema: docs/analyzer-contract.md
      │
┌─────────────────┐   agent: complexity-analyzer
│  2. COMPLEXITY  │   .claude/complexities/run_pipeline.py
└─────────────────┘   discover → order → gate → run → merge
      │
      ▼  complexity_artifact.json  +  one report per complexity
```

Stage 2 never sees source text. That is what makes the same 20 analyzers score
COBOL, PL/SQL and Java without modification.

## Directory map

```
adaptive-legacy-code-complexity-harness/
│
├── CLAUDE.md                       Project memory. Loaded into every Claude Code
│                                   session: commands, conventions, the rules.
├── README.md                       This file.
│
├── .claude/                        ⚠ Contains PRODUCT CODE, not just tool config
│   │
│   ├── settings.json               Shared permissions. Checked in. Denies all
│   │                               access to plsql_to_brd/.
│   │
│   ├── agents/                     WHO orchestrates
│   │   ├── 1_inventory_agent.md      name: java-inventory
│   │   └── 3_complexity_agent.md     name: complexity-analyzer
│   │
│   ├── rules/                      Path-scoped instructions. Load only when
│   │   └── analyzer-code.md        touching *.py under complexities/ or tools/.
│   │
│   ├── skills/                     WHAT each complexity is, and WHEN to use it
│   │   ├── cyclomatic-complexity/SKILL.md
│   │   ├── runtime-complexity/SKILL.md
│   │   └── … 20 in total, one per complexity
│   │
│   ├── complexities/               HOW each complexity is computed  ← product code
│   │   ├── _core.py                The shared contract. Read this first.
│   │   ├── 01_…20_*.py             One implementation per skill, paired by number
│   │   ├── run_pipeline.py         The runner
│   │   └── _superseded_style_a/    Original Style-A analyzers, preserved
│   │
│   └── inventory/                  Stage 0                        ← product code
│       └── scanner.py              Java repo scanner
│
├── docs/
│   ├── system-overview.md          Start here
│   ├── inventory-contract.md       Shape of inventory_artifact.json
│   ├── analyzer-contract.md        How to build complexity #21
│   └── architecture-decisions.md   Why it is built this way, and what would reverse it
│
├── samples/
│   └── cobol_payroll.tree.json     Reference tree. Exercises every field.
│
└── tools/
    ├── judge.py                    Audits the analyzers — 10 adversarial checks each
    ├── 99_canary_complexity.py     Defective on purpose; proves the judge has teeth
    └── tree_bridge.py              Converts legacy Style-A trees
```

## The three layers, and why they are separate

| Layer | Answers | Lives in | Changes when |
|---|---|---|---|
| **Agent** | How do I run the whole thing? | `.claude/agents/` | The workflow changes |
| **Skill** | What is this complexity, when do I use it? | `.claude/skills/` | The concept changes |
| **Implementation** | How is the number computed? | `.claude/complexities/` | The algorithm changes |

Skill *N* pairs with implementation *N* by number:
`skills/runtime-complexity/` ↔ `complexities/17_runtime_complexity.py`.

Nothing holds a list of the 20. The agent and pipeline **discover** them by scanning
`.claude/complexities/[0-9][0-9]_*.py` and reading each file's `SPEC`. Drop in
`21_*.py` and it joins the next run with no edit anywhere else.

> **`.claude/` is not editor configuration here.** It holds the deliverable.
> Deleting it deletes the product. This is a deliberate choice matching the
> `plsql_to_brd` house convention; see `docs/architecture-decisions.md`.

## Execution order

Bands are absolute. Within a band: dependency depth, then number — the numeric
tie-break is what makes two runs over the same tree produce an identical plan.

```
size → structural → data → coupling → hazard → composite
```

`size` runs first because later bands divide by it; computing it once centrally
stops five analyzers deriving five slightly different sizes. `composite` runs last
because Maintainability consumes size and branching, and Migration consumes
Database, Testability, Runtime and Architectural — they cannot run earlier.

## Stage 0 has no skills, deliberately

Inventory is one deterministic scan, not twenty selectable analyses. There is
nothing to discover or choose among at runtime, so it has a scanner and no
`skills/` directory. Adding one would imply a choice that does not exist.

```bash
python .claude/inventory/scanner.py --repo-root <path-to-java-repo> -o out
```

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
