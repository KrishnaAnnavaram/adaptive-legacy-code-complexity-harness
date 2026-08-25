# BankingSystem → Python — Target-Fit Complexity Report

**Source language:** Java  **Target language:** Python
**Produced by:** the `target-fit-complexity` skill (invoked by the Complexity Agent, `3_complexity`, because a target language was named)
**Artifact:** `outputs/BankingSystem/target/python/complexity_artifact.json`

> ⚠️ **The Python descriptor is UNREVIEWED (`"reviewed": false`).** Every score
> in this report is **provisional** and the artifact's own confidence is
> reduced to **0.6** for that reason. A descriptor is only trusted at full
> confidence after a human checks each capability field against real language
> documentation and promotes it out of `.claude/target_fit/languages/_pending/`.
> Read every number below with that caveat in mind.

---

## What this report answers

Not "how complex is the Java code" — that is the source-side report. This one
answers: **if BankingSystem's destination is Python, what does each of the 20
complexity measurements actually come out to, computed for real against a tree
that honestly represents what survives translation?**

The numbers here are **independently computed**, not carried forward from the
Java run. The skill builds a *projected tree* (what a faithful Python translation
would structurally look like) and runs the **same 20 analyzers** against it. The
Java results are read only to build the side-by-side comparison — never to
produce a Python score.

---

## How the tree was projected onto Python

Three generic, descriptor-driven rules fired (nothing here is hardcoded to
Java-or-Python):

| Rule | What it does | Result for BankingSystem → Python |
|---|---|---|
| **Jump constructs** | Drop any unit whose control flow uses a construct the target can't express (`GOTO`/`ALTER`/…) | **0 units dropped** — BankingSystem uses no such jumps, and Python could express them anyway |
| **Object model** | Drop `types` if the target has no class model | **Not dropped** — Python has classes (`multiple_inheritance` is not null) |
| **Volume fields** | Strip `loc`, `comment_lines`, `halstead` from every unit, always | **Stripped from all 38 units** — there is no honest way to project the size of code that doesn't exist yet |

**Projection outcome: 38 / 38 units kept, 0 dropped.** A faithful Python
translation of this codebase preserves every unit's structure.

The stripped volume fields are the *only* reason any Python number differs from
the Java baseline — see the two affected metrics below.

---

## Coverage: 17 of 20 measured (85%)

| | |
|---|---|
| **Measured** | 17 |
| **Not measured (insufficient_input)** | 3 — Maintainability (#11), Database (#15), Configuration (#18) |
| **Errors** | 0 |
| **Overall level** | **L5 (severe)** — the single worst finding anywhere (Data Flow) |
| **Average level** | **2.12** — between L2 (low) and L3 (moderate); the typical severity across measured dimensions |
| **Mean confidence** | 0.92 (per-analyzer); **artifact confidence 0.6** because the descriptor is unreviewed |

The worst-case (L5) and average (2.12) diverge because there is one genuine
hotspot — Data Flow — dragging the maximum up while most dimensions sit at L1–L2.

---

## Per-metric results (Python target)

Each metric's method is unchanged from the source-side analyzer; only the input
tree differs. Every number below is exactly what the projected-tree run produced.

### Measured

- **07 Structural — L2, score 0.32** (confidence 0.85). *38 units, 1,149 lines;
  top 3 units hold 32% of the code; 4 outliers.* `loc` was stripped, so this ran
  in **degraded mode**, reading size from control-flow-node counts and
  `start_line`/`end_line` spans instead — confidence dropped, result unchanged.
- **01 Cyclomatic — L1, score 5.0** (confidence 0.9). Max v(G) 5; 70 test cases
  for full branch coverage; 0 units above threshold. Decision points survive
  translation, so this is identical to Java.
- **02 Cognitive — L2, score 8.0** (confidence 0.9). Max cognitive 8; difficulty
  is branch *count*, not nesting.
- **03 Control Flow — L1, score 0.0** (confidence 0.8). 38/38 units fully
  structured; 0 not mechanically translatable; 0 contain `ALTER`.
- **05 Nesting — L1, score 2.0** (confidence 1.0). Deepest nesting 2; 33 units
  completely flat.
- **06 NPath — L1, score 16.0** (confidence 0.85). Worst NPath 16; 0 units beyond
  exhaustive path testing.
- **17 Runtime — L3, score 25.0** (confidence 1.0). 0 super-linear; 0 with I/O or
  SQL inside a loop; **1 recursive** (the L3 driver — recursion depth is
  statically unprovable, flat +20).
- **12 Data Flow — L5, score 144.0** (confidence 1.0). **The most severe finding.**
  Max data-flow score 144; 11 shared data elements; **9 data-heavy units** — the
  GUI Swing forms that all read/write the same shared state. This is a property
  of *what the code does*, so it transfers to Python unchanged.
- **04 Coupling — L1, score 4.0** (confidence 1.0). 0 hubs; 35 independently
  extractable; 10 isolated.
- **08 Cohesion — L2, score 2.0** (confidence 1.0). 21 types; worst LCOM4 2; 0
  low-cohesion types.
- **09 Dependency — L3, score 45.7** (confidence 1.0). 50 modules; 115 external
  dependencies; longest chain 3; 0 cycles. *(Note: the dependency edges are the
  Java `javax.swing`/`java.awt` surface carried through the tree unchanged; a
  real Python port would target different libraries — this is a projection of the
  current dependency shape, not a mapped Python one.)*
- **10 Change Impact — L2, score 0.11** (confidence 1.0). 0 high-impact; worst
  change reaches ~10% of the system.
- **13 Inheritance — L2, score 2.0** (confidence 1.0). Max depth 2; widest base
  has 2 children; 0 deep hierarchies. Python kept `types`, so this measured.
- **14 Interface / API — L3, score 36.2** (confidence 1.0). 34 exposed
  operations; avg 0.88 params/op; L3 driven by count, not per-op complexity.
- **20 Architectural — L1, score 7.2** (confidence 0.9). 0 dependency cycles; 0
  layering violations; 1 hub unit.
- **16 Testability — L3, score 24.0** (confidence 1.0). ~70 test cases; **4 units
  blocked or hostile to isolation** (the friction, not the burden, drives L3).
- **19 Migration — L3, score 21.0** (confidence **0.5**). 1 unit requires
  rearchitecture; **0 translation blockers**. See the note below — this score
  moved down from the Java baseline (23.6) for a reason that is **not** a genuine
  reduction in effort.

### Not measured (honest gaps, not zeros)

- **11 Maintainability — insufficient_input.** Requires `loc`, which projection
  strips from every unit. Rather than emit a misleading `0`, the analyzer gates —
  **this is the designed, correct behavior**: there is no honest Maintainability
  Index for code that does not exist yet. (On the Java source it was L5 · 37.8.)
- **15 Database — insufficient_input.** Tree carries no `sql`/`cursors`/
  `transactions`. Same as the Java source — not Python-specific.
- **18 Configuration — insufficient_input.** Tree carries no `config_reads`/
  `literals`/`conditional_compilation`/`feature_flags`. Same as the Java source.

---

## The one score that moved — and why it is not a real finding

**Migration Complexity dropped 23.6 → 21.0** and its "plausibly automatable"
figure fell from ~12% to ~3%. This is **not** evidence that Python is easier to
migrate to. Migration declares `loc` as an **optional** input; when projection
strips `loc`, the analyzer's own existing code substitutes zero for the missing
volume rather than gating, which shifts the volume component. The report says so
itself — its `confidence.reasons` name `loc` (and `sql`, `platform_calls`,
`dynamic_constructs`, `conditional_compilation`) as absent, and confidence is
0.5. **Treat this delta as a stripped-optional-field artifact, not a
target-language improvement** (see `docs/target-fit-contract.md`, "the one sharp
edge").

Every other measured metric is **identical** to the Java source, which is the
expected and correct result: they count decision points, call structure, shared
state, and hierarchy — facts about what the code *does*, all of which survive a
faithful translation intact.

---

## Bottom line

- A faithful Python port of BankingSystem keeps **every unit** (nothing is
  untranslatable) and lands at the same overall severity — **L5**, driven
  entirely by the **shared-state data-flow hotspot in the 9 GUI Swing forms**,
  which no change of target language fixes.
- **Maintainability cannot be scored for a target** without real target code, and
  the harness says so instead of guessing.
- **Migration's lower number is an artifact of stripped volume fields**, not a
  real saving — read it with the 0.5 confidence and the caveat above.
- All scores are **provisional** until the Python descriptor is human-reviewed
  and promoted.
