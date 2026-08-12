# Complexity Report — samples/java_bank

Source: `D:/adaptive-legacy-code-complexity-harness/samples/java_bank`

This report is the prose companion to `complexity_artifact.json`. Every
number below is pulled from that artifact or from the individual skill
reports in `reports/`; nothing here is re-scored or estimated fresh.

## Codebase at a glance

The tree covers **36 units** across **12 types** (8 classes, 2 interfaces, 1
enum, and one nested class — `TransactionLog$Entry`), written in **Java**.
The upstream inventory scan (`inventory_artifact.json`) reports
**11 files scanned** in the repository.

- **Overall level: L3** (moderate)
- **Mean level across measured skills: 1.94** (between L1 and L2 on the raw
  per-skill average — the L3 overall banding reflects where the worst
  individual skills landed, not the average)
- **Mean confidence: 0.93**
- **Coverage: 18 of 20 skills measured (90%)** — Database Complexity (#15)
  and Configuration Complexity (#18) did not run because the tree carries
  none of the fields either one requires. See "Skills not measured" below.

## What was measured, and why

| Tier band | Skills that ran | Why it matters here |
|---|---|---|
| **1 size** | Structural Complexity (#7) | Establishes the shape of the estate before anything else — how big it is and whether size is concentrated in a few units. |
| **2 structural** | Cyclomatic (#1), Cognitive (#2), Control Flow (#3), Nesting (#5), NPath (#6), Runtime (#17) | The core per-unit readability, testability and execution-cost signals — how many paths exist, how hard they are to follow, and what they cost to run. |
| **3 data** | Data Flow (#12) | Surfaces which units carry the heaviest data-movement and shared-state pressure — the units hardest to reason about in isolation. |
| **4 coupling** | Coupling (#4), Cohesion (#8), Dependency (#9), Change Impact (#10), Inheritance (#13), Interface/API (#14), Architectural (#20) | Answers what can be moved, extracted or decomposed, and what a change to one unit puts at risk elsewhere. |
| **5 hazard** | *(none — see below)* | Would surface the two riskiest hidden-behaviour surfaces in a legacy estate: the database relationship and the configuration surface. Neither could be measured here. |
| **6 composite** | Maintainability (#11), Testability (#16), Migration (#19) | Rolls the primitives above into the three questions a modernization programme is actually funded to answer: is this maintainable, can it be safely tested, and what does moving it cost. |

## Per-complexity findings

### Structural Complexity (#7) — size

**What it is.** The shape and size of the codebase: how much there is, how
it is distributed, and whether that distribution is healthy.

**Why it matters here.** Every other metric in this report scores a single
unit at a time. This is the only one that reports the shape of the whole
estate — whether its 184 lines are spread evenly or concentrated in a
handful of large units, which is what actually drives how a migration would
be sequenced.

**What we found.** Level **L1** (trivial), score **0.23**, confidence
**0.85** (reduced because the tree carries no `comment_lines`). Across 36
units totalling 184 lines, the top 3 units — `Bank.transfer` (16 loc),
`TransactionLog.linked` (15 loc) and `Bank.describe` (12 loc) — hold 23% of
the code (`concentration_top_decile` 0.234), and 3 units are flagged as
outliers. An L1 result means the codebase is not dominated by a small
number of oversized units; there is no single paragraph or method that a
migration plan would need to treat as a special case on size alone.

### Cyclomatic Complexity (#1) — structural

**What it is.** The number of linearly independent paths through a unit —
the lower bound on how many test cases are needed for full branch coverage.

**Why it matters here.** It is the number every estimate conversation
starts with, and the most widely understood complexity metric there is.

**What we found.** Level **L1** (trivial), score **4.0**, confidence
**1.0**. Across the 36 units, the most branch-heavy ones — `Bank.transfer`
and `TransactionLog.totalFor` — each have v(G) = 4, so even the worst unit
in the codebase needs only 4 test cases for full branch coverage. Covering
every branch across the whole codebase takes 56 test cases in total, and
**0 units** crossed the threshold this analyzer flags as worth a second
look. This is not a testing burden on its own terms.

### Cognitive Complexity (#2) — structural

**What it is.** How hard a unit is for a human to read and hold in their
head — distinct from cyclomatic complexity, which only counts paths and is
blind to where they sit (flat vs. deeply nested).

**Why it matters here.** It is the metric that would separate a flat
20-branch switch from a 4-deep nest of ifs that scores the same v(G) — one
is skimmable, the other is not.

**What we found.** Level **L1** (trivial), score **4.0**, confidence
**1.0**. The worst unit, `TransactionLog.totalFor`, scores a cognitive
complexity of 4 — identical to its cyclomatic complexity of 4
(`gap_vs_cyclomatic` 0) — meaning its difficulty comes from branch count,
not from nesting. **0 units** in the codebase are hard because of nesting
rather than branch count, so there is nothing here that flattening would
meaningfully improve; the branch-count contributors are already accounted
for by the cyclomatic result above.

### Control Flow Complexity (#3) — structural

**What it is.** How structured the flow is — whether it reduces to clean
nested blocks or contains jumps that make it irreducible. This is the
metric that decides whether automated translation of a unit is even
possible.

**Why it matters here.** Cyclomatic complexity says how many tests a unit
needs; this says whether the unit can be mechanically restructured at all.

**What we found.** Level **L2** (low), score **1.0**, confidence **0.8**
(the report is explicit that it computes an unstructuredness index from
jump constructs rather than true McCabe ev(G), because a CFG node tree
carries no edges to reduce). All **36 of 36 units are fully structured**,
none block translation, and none contain `ALTER`. One unit,
`Bank.transfer`, is flagged L2 for carrying 3 exit points rather than 1 —
still `mechanically_translatable: true`, just not the cleanest single-exit
shape. Everything else in the codebase sits at L1.

### Nesting Complexity (#5) — structural

**What it is.** How deeply control structures are stacked inside one
another — the cheapest reliable predictor of reading difficulty, and the
thing cyclomatic complexity is blindest to.

**Why it matters here.** Twenty flat branches and four branches nested four
deep can carry the same v(G); only nesting depth tells them apart.

**What we found.** Level **L1** (trivial), score **2.0**, confidence
**1.0**. The deepest nesting anywhere in the codebase is 2, reached by
`TransactionLog.totalFor` (an `OR` construct at depth 2). **31 of 36
units are flat** (no nesting at all), and **0 units** sit at depth 4 or
beyond, the threshold this analyzer treats as excessive. Nothing here needs
flattening.

### NPath Complexity (#6) — structural

**What it is.** The number of distinct acyclic execution paths that
actually exist through a unit — different from cyclomatic complexity, which
only counts the paths needed to cover every edge.

**Why it matters here.** It is the gap between "we have full branch
coverage" and "we tested the combinations."

**What we found.** Level **L1** (trivial), score **8.0**, confidence
**0.85** (the report notes NPath assumes independent branches, so the true
reachable count may be lower — this is reported as an upper bound). The
worst units, `Bank.transfer` and `TransactionLog.totalFor`, each have an
NPath of 8 against a cyclomatic complexity of 4 (`paths_per_branch_test`
2.0) — meaning branch coverage for those two units leaves half their path
combinations still untested. **0 units** are beyond exhaustive path
testing; the whole codebase remains fully testable in the combinatorial
sense, not just the branch-coverage sense.

### Runtime Complexity (#17) — structural

**What it is.** The expected cost of executing the code — its algorithmic
growth class and the work it does per unit of input, as opposed to how hard
it is to read or change.

**Why it matters here.** A unit can be trivially readable and still not
survive a data-volume increase; this is the only metric here that looks at
execution cost rather than comprehension cost.

**What we found.** Level **L3** (moderate), score **20.2**, confidence
**1.0** at the report level (individual units carry lower per-item
confidence, averaging 0.76, because the CFG carries no operation-cost nodes
for most units and no loop carries an explicit `bounded` flag). Of the 36
units, 30 are `O(1)`, 5 are `O(n)`, and **1 is recursive**:
`CompoundInterestPolicy.rate`, flagged O(n) recursive and scoring 20.2 — the
single score that sets the whole skill's level to L3, with the explicit
reason "recursive — termination and depth need explicit review." The five
`O(n)` units (`AccountType.forBalance`, `InterestPolicy.annualRate`,
`SavingsAccount.applyInterest`, `TransactionLog.totalFor`, and one more)
carry reduced confidence (0.65) because their loops carry no `bounded` flag
— the growth estimate is inferred from nesting alone and may overstate
units that actually iterate a fixed-size structure. **0 units** are
super-linear and **0** mix I/O or SQL with a loop.

### Data Flow Complexity (#12) — data

**What it is.** How values and data move across statements, functions and
modules — the transformations, side effects and data dependencies that make
code hard to reason about.

**Why it matters here.** It is the only metric here that scores state
coupling directly, rather than call coupling.

**What we found.** Level **L3** (moderate), score **16.0**, confidence
**1.0**. The worst unit, `Bank.transfer`, scores 16.0 — driven by 8
outbound calls fanning out from a single 3-parameter entry point, even
though it touches only 1 data reference directly. Across the codebase there
are **10 shared data elements** — state that more than one unit touches —
and **0 units** are flagged as data-heavy against this analyzer's own
threshold. The `Account` module carries the highest per-module data-flow
pressure (43.0), consistent with it being the most-shared piece of state in
the estate.

### Coupling Complexity (#4) — coupling

**What it is.** How tightly units are bound to each other — what decides
whether a unit can be moved or extracted on its own.

**Why it matters here.** A unit can be internally simple and still be
impossible to extract if enough other units call it; every decomposition
plan is really a coupling argument.

**What we found.** Level **L3** (moderate), score **36.0**, confidence
**1.0**. The worst unit, `Account.withdraw`, has an information-flow score
of 36 (fan-in 2, fan-out 3 — Henry & Kafura `(fan_in * fan_out)^2`).
Encouragingly, **0 units are hubs** (called by many and calling many —
the hardest role to remove), **33 of 36 units (91.7%) are independently
extractable**, and **15 units are isolated** (no inbound or outbound calls
at all, free to move or candidates for dead-code review). `Bank.transfer`
is the one `orchestrator` in the codebase (fan-out 6) — it can only move
together with what it calls.

### Cohesion Complexity (#8) — coupling

**What it is.** How closely related the responsibilities inside a class
are — measured via the LCOM family, using how much each type's methods
share the same fields.

**Why it matters here.** Low cohesion signals a class doing more than one
job, which is exactly what makes a class hard to split cleanly during a
decomposition.

**What we found.** Level **L3** (moderate), score **3.0**, confidence
**1.0**. Of 12 types, the worst LCOM4 is 3, reached by two types: `Bank`
(5 methods, 2 fields, `lcom_hs` 0.875) and `util.Validation` (3 methods, 0
fields, `lcom_hs` 1.0). Both are flagged as low-cohesion (>= 3 independent
method clusters). For `Validation` this is expected — it is a static
utility class with no shared state, so its methods were never going to
cluster. For `Bank`, an LCOM4 of 3 means its methods already draw the lines
along which it could be split into 3 smaller, more focused types.

### Dependency Complexity (#9) — coupling

**What it is.** Internal, external, library, API, DB and platform
dependencies of the codebase — a major driver of migration effort and
upgrade risk.

**Why it matters here.** It reads the dependency graph directly rather than
the call graph, so it captures import- and inheritance-level coupling that
coupling complexity does not.

**What we found.** Level **L2** (low), score **29.6**, confidence **1.0**.
Across 16 modules there are 10 total dependency edges: 4 internal and 6
library (all `java.util` collection types). The external ratio is 0.6, the
longest dependency chain is 2 hops, and **0 dependency cycles** were found.
Several modules — `Bank`, `TransactionLog`, `CompoundInterestPolicy`,
`SavingsAccount` — show maximum instability (1.0: they depend on others but
nothing depends on them), which is typical of leaf-level orchestration
code and not itself a red flag.

### Change Impact Complexity (#10) — coupling

**What it is.** How widely a change to one component can ripple through
the system — its "blast radius," computed via reverse reachability over
the call and dependency graphs.

**Why it matters here.** It answers "if I touch this, what else must be
retested" before a change is made, not after.

**What we found.** Level **L2** (low), score **0.1**, confidence **1.0**.
Across 52 components (units plus types), **0 are high-impact**, and the
worst single change — to `Account.audit`, called by 4 other units — has a
blast radius of 5 components, or 9.8% of the system
(`impact_ratio` 0.098). `Validation.requirePositive` is the next
highest at an impact ratio of 0.078. No change anywhere in this codebase
would require retesting more than a tenth of the system.

### Inheritance Complexity (#13) — coupling

**What it is.** Complexity introduced by inheritance hierarchies — depth of
inheritance tree (DIT) and number of children (NOC), the classic OO
hierarchy metrics.

**Why it matters here.** Deep or wide hierarchies make behavior hard to
trace, since understanding a leaf class means reading its whole ancestor
chain.

**What we found.** Level **L1** (trivial), score **1.0**, confidence
**1.0**. Of 12 types, the maximum inheritance depth is 1 — only
`SavingsAccount` extends anything (`Account`) — and the widest base class
has 1 child. **0 deep hierarchies** were found. This is about as shallow as
an inheritance graph gets; there is no ancestor-chain reading tax anywhere
in this codebase.

### Interface / API Complexity (#14) — coupling

**What it is.** Complexity of the interfaces, endpoints and contracts the
system exposes — operation count, parameter width, schema count, and
external contract edges.

**Why it matters here.** A wide contract surface is expensive to change,
because every consumer of that surface has to be found and re-tested.

**What we found.** Level **L3** (moderate), score **35.8**, confidence
**1.0**. The tree exposes **33 operations** with an average of 1.12
parameters each; the widest is the `SavingsAccount` constructor at 4
parameters. There are **0 distinct schemas** and **0 external API
contracts** — this is an internal object model, not a service boundary, so
the L3 level here reflects breadth of exposed methods in a small codebase
where nearly everything is public, rather than genuine integration risk.

### Architectural Complexity (#20) — coupling

**What it is.** Structural quality of the system above the unit level — how
modules depend on each other, whether layers hold, and where the natural
seams are for decomposition.

**Why it matters here.** A codebase of clean units can still be
architecturally unsplittable, and vice versa; this is the only metric that
looks at the system, not the unit.

**What we found.** Level **L1** (trivial), score **0.9**, confidence
**0.9** (reduced because the tree carries no `layers` declaration, so
layering violations could not be checked). Across 16 modules there are
**0 dependency cycles**, **0 layering violations** (the dimension itself
is unevaluated for lack of a layer declaration, not evaluated-and-clean),
and **0 hub units**. This is a decomposable codebase with no structural
obstacle currently visible — though the layering dimension is a genuine
blind spot here, not a clean result, until layer information is supplied.

### Maintainability Complexity (#11) — composite

**What it is.** Overall difficulty of maintaining the code over time,
combining size, cyclomatic complexity, Halstead volume and comment density
into the industry-standard Maintainability Index.

**Why it matters here.** It is the standard composite figure for
takeover and technical-debt conversations, transparent about which
component is driving a low score.

**What we found.** Level **L3** (moderate), score **68.0** (out of 100;
higher is better for this metric — `direction: lower_is_worse`), confidence
**0.7** (Halstead volume is estimated rather than measured, and comment
density could not be scored — both optional inputs are absent from the
tree). The LOC-weighted Maintainability Index across all 36 units is 68.0.
The single worst unit is `Bank.transfer` at an MI of 54.3 — still within
the L3 "moderate" band, not flagged as hard-to-maintain (**0 units**
crossed that threshold). Because Halstead volume is estimated rather than
supplied, this figure should be read as directionally sound rather than
precise.

### Testability Complexity (#16) — composite

**What it is.** How hard it is to get a unit under test at all, separating
test burden (how many paths need covering) from test friction (hidden
inputs, shared-state writes, missing seams, non-determinism).

**Why it matters here.** Modernization is only safe behind a
characterization-test net, and friction — not burden — is what actually
blocks writing that net.

**What we found.** Level **L3** (moderate), score **19.0**, confidence
**1.0**. Roughly 56 test cases are needed for branch coverage across the
codebase (matching the cyclomatic-complexity total), and **0 units** are
`blocked` or `hostile` to isolation — all 36 units are classified
`tractable`. The worst unit by friction is the `Account` constructor, at a
testability score of 19.0, driven by 3 hidden inputs not passed as
parameters and 3 writes to shared state a test would need to reset.
`Bank.transfer` (score 14.0) is friction-heavy for a different reason: 6
collaborators would need to be stubbed to isolate it. **26 of 36 units**
have at least one hidden input — reading state that is not passed in as a
parameter — which is the dominant friction source across the estate, even
though it is not severe enough anywhere to block a test outright.

### Migration Complexity (#19) — composite

**What it is.** The effort and risk of moving this code to a different
language, runtime or platform, scoring volume (how much there is to move)
separately from blockers (what defeats automated translation), then mapping
the result onto a migration strategy.

**Why it matters here.** This is the question a modernization programme is
funded to answer, and every other analyzer in this report feeds into it.

**What we found.** Level **L1** (trivial), score **4.1**, confidence
**0.6** — the lowest confidence of any measured skill, because four
optional inputs (`sql`, `platform_calls`, `dynamic_constructs`,
`conditional_compilation`) are all absent, and the report's own caveat says
its database and configuration contributions were estimated rather than
supplied by reports #15 and #18 (which did not run — see below). All 36
units are recommended for the **`rehost`** strategy (move as-is, no
structural obstacle found); **0 units** require refactor, rearchitecture or
a rebuild, and **0 translation blockers** were found. Roughly 18% of the
migration work is plausibly automatable (`portfolio_automatable_fraction`
0.18). The worst-scoring unit is again `Bank.transfer` (4.1), combining the
highest volume score (1.1, from its 16 lines) with the flat blocker score
of 3.0 several units share. Given the confidence caveat, this should be
read as a directionally sound "nothing structurally blocks translation"
finding rather than a costing-grade figure — a full run would need SQL,
platform-call and conditional-compilation data the tree does not carry.

## Skills not measured

**Database Complexity (#15)** would have scored how hard this codebase's
relationship with persistent data is to understand, change and migrate —
SQL surface, schema reach, statement shape, dynamic SQL, and transaction
control, plus access-pattern penalties like SQL executed inside a loop.
It did not run because the tree carries none of `sql`, `cursors`, or
`transactions` — the analyzer requires at least one. Concretely: this
means the Java parser that produced the tree is not yet capturing JDBC
calls (`executeQuery`, `prepareStatement`, ORM query annotations) as `sql`
entries on the units that make them. Until that is added, this codebase's
actual database exposure is simply unknown, not measured-clean.

**Configuration Complexity (#18)** would have scored how much of the
system's behaviour is decided outside the source code — external
configuration surface, build variants from conditional compilation,
hardcoded values that should be configuration, and how scattered
configuration reads are. It did not run because the tree carries none of
`config_reads`, `literals`, `conditional_compilation`, or `feature_flags` —
the analyzer requires at least one. Concretely: the parser is not yet
capturing `System.getProperty`/`System.getenv`/`@Value`-style reads as
`config_reads`, nor literal constants as `literals`. Until it does, whether
this codebase hides environment-dependent behaviour is unknown, not
measured-clean.

## Closing summary

This codebase lands at an overall **L3 (moderate)** with a high mean
confidence (0.93) across the 18 skills that could run. Nothing here is
severe: every measured skill topped out at L3, no unit was ever flagged L4
or L5, and consequently the artifact's cross-skill hotspot list is empty —
no unit shows convergent risk across two or more independent skills, which
is the bar this harness uses before calling something a hotspot. The
findings that most deserve attention are individually L3, not corroborated:
**Runtime Complexity**, driven by one recursive unit
(`CompoundInterestPolicy.rate`) whose termination the analyzer explicitly
flags as needing manual review, plus several loop-growth estimates run at
reduced confidence because the tree carries no `bounded` flag on loops;
**Coupling** and **Data Flow**, both centered on `Account.withdraw` and
`Bank.transfer` respectively as the most state- and call-entangled units;
and **Cohesion**, where `Bank` splits cleanly into 3 independent method
clusters if a decomposition were ever wanted. Set against all of that:
coverage is **18 of 20 (90%)**, not 20 of 20 — Database Complexity and
Configuration Complexity did not run for lack of SQL and configuration
signal in the tree, and Migration Complexity's own confidence (0.6, the
lowest of any measured skill) is a direct consequence of that same gap.
Nothing in this report should be read as "no database or configuration
risk" — it should be read as "not measured yet."
