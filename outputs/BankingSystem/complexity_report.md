# Complexity Report — BankingSystem

Source: `D:/adaptive-legacy-code-complexity-harness/input/BankingSystem`

## Codebase at a glance

This is a small Java Swing desktop application: 21 files scanned (`inventory_artifact.json` → `total_files_scanned: 21`, all 21 are `.java`, 21 types, 4 packages), normalized into 38 analyzable units and 21 types across 1,149 lines of code. The tree declares its language as `java`.

**Overall level: L5 (severe).** Mean level across measured skills is 2.28, mean confidence is 0.93. Coverage is **18 of 20 skills measured (90%)** — two skills, Database Complexity (#15) and Configuration Complexity (#18), did not run because the tree carries none of the fields they need (`sql`/`cursors`/`transactions` for #15; `config_reads`/`literals`/`conditional_compilation`/`feature_flags` for #18). Both report `insufficient_input`, not a zero — the harness does not fabricate a clean result out of missing data. Nine units are flagged as corroborated hotspots (two or more independent skills banding them L4/L5), and the L5 overall level is driven concretely by two composite/data findings below, not by an averaging artifact.

## What was measured, and why

| Tier band | Skills that ran | Why it matters here |
|---|---|---|
| 1 — size | Structural Complexity (#7) | Reports the SHAPE of the estate — whether the 1,149 lines are spread evenly or concentrated in a few large units, which is what a migration plan should be built around. |
| 2 — structural | Cyclomatic (#1), Cognitive (#2), Control Flow (#3), Nesting (#5), NPath (#6), Runtime (#17) | Together these answer how many tests each unit needs, how hard it reads, whether it can be mechanically restructured, how deeply it nests, how many path combinations exist behind "full branch coverage," and how it will behave under growing data volume. |
| 3 — data | Data Flow (#12) | Reveals how values and shared state move across units — the coupling that isn't visible in a call graph. |
| 4 — coupling | Coupling (#4), Cohesion (#8), Dependency (#9), Change Impact (#10), Inheritance (#13), Interface/API (#14), Architectural (#20) | Together these decide what can be moved, split, or safely changed: binding between units, responsibility mixing inside classes, the external dependency surface, blast radius of a change, inheritance depth, contract surface, and system-level decomposition seams. |
| 5 — hazard | *(none ran)* Database (#15), Configuration (#18) | Database complexity would show where business logic hides in SQL/schema coupling; Configuration complexity would show how much behaviour is decided outside the code. Neither could be measured — see "Skills not measured" below. |
| 6 — composite | Maintainability (#11), Testability (#16), Migration (#19) | These roll the primitives above into takeover-readiness, test-net feasibility, and migration strategy/effort — the numbers a modernization programme is actually funded to answer. |

## Per-complexity findings

### Structural Complexity (#7) — size

**What it is.** The shape and size of the codebase: how much there is, how it is distributed, and whether that distribution is healthy.

**Why it matters here.** A mean hides the outliers that are the actual migration risk; this codebase's 1,149 lines are not evenly spread.

**What we found.** Headline: "38 unit(s), 1,149 line(s); top 3 unit(s) hold 32% of the code; 4 outlier(s)." Score 0.32, level **L2 (low)**. The largest units — `GUI.Menu.Menu` (129 LOC), `GUI.AddStudentAccount.AddStudentAccount` (121 LOC), `GUI.AddCurrentAccount.AddCurrentAccount` (116 LOC), `GUI.WithdrawAcc.WithdrawAcc` (115 LOC) and `GUI.AddSavingsAccount.AddSavingsAccount` (111 LOC) — together hold roughly a third of all code, well below the 0.60 threshold at which an estate becomes "a handful of huge units plus noise." Confidence is 0.85, lowered because `comment_lines` is absent from the tree (comment ratio could not be computed).

**Hotspots.** Ten units are listed as size hotspots, all GUI form classes (`Menu`, `AddStudentAccount`, `AddCurrentAccount`, `WithdrawAcc`, `AddSavingsAccount`, `DepositAcc`, `AddAccount`, `Login.initialize`, `Bank.Bank.display`, `DisplayList`) — none individually alarming, but this is the same set that recurs across the composite findings below.

### Cyclomatic Complexity (#1) — structural

**What it is.** The number of linearly independent paths through a unit — the lower bound on how many test cases are needed for full branch coverage.

**Why it matters here.** It's the number every estimate conversation starts with.

**What we found.** Headline: "38 unit(s); max v(G) 5; 70 test case(s) needed for branch coverage; 0 unit(s) above threshold." Score 5.0, level **L1 (trivial)**, confidence 1.0. The single most branch-heavy method is `Bank.Bank.withdraw` at v(G)=5, so even the worst method in the codebase needs only 5 test cases for full branch coverage, and covering every branch across all 38 units takes 70 test cases total. No unit crossed the threshold this analyzer flags as worth a second look.

**Hotspots.** None — the report carries an empty hotspot list; nothing here reached a level worth flagging on its own.

### Cognitive Complexity (#2) — structural

**What it is.** How hard a unit is for a human to READ and hold in their head — penalising nesting in a way cyclomatic complexity does not.

**Why it matters here.** It separates a skimmable branch-heavy method from a genuinely hard-to-follow nested one.

**What we found.** Headline: "38 unit(s); max cognitive 8; 0 unit(s) hard because of NESTING rather than branch count." Score 8.0, level **L2 (low)**, confidence 1.0. The hardest-to-read unit is `Data.FileIO.Read` (cognitive score 8, v(G) 5), with the largest gap between cognitive and cyclomatic complexity in the codebase (gap of 3) — but that unit's own `difficulty_driver` is still recorded as branch count, not nesting, and no unit anywhere in the codebase is flagged as nesting-driven. This is a codebase that reads roughly as hard as it tests.

**Hotspots.** None listed.

### Control Flow Complexity (#3) — structural

**What it is.** How STRUCTURED the flow is — whether it reduces to clean nested blocks or contains jumps that make it irreducible to automated translation.

**Why it matters here.** This is the number that decides whether a unit can be mechanically restructured at all, not just how many tests it needs.

**What we found.** Headline: "38/38 unit(s) fully structured; 0 not mechanically translatable; 0 contain ALTER." Score 0.0, level **L1 (trivial)** — every one of the 38 units is fully structured with zero jump constructs. Confidence is 0.8, and the report is explicit about why: what's computed here is an "unstructuredness index" derived from jump constructs present in the tree, not true McCabe ev(G), because the CFG the tree carries is a node tree with no edges to collapse. It is a sound, deliberately conservative proxy, but the report does not claim to be measuring true essential complexity.

**Hotspots.** None.

### Nesting Complexity (#5) — structural

**What it is.** How deeply control structures are stacked inside one another — the cheapest reliable predictor of reading difficulty, and the thing v(G) is blindest to.

**Why it matters here.** Twenty flat branches and four branches nested four deep can carry the same v(G); only nesting depth tells them apart.

**What we found.** Headline: "38 unit(s); deepest nesting 2; 0 unit(s) at depth >= 4; 33 flat." Score 2.0, level **L1 (trivial)**, confidence 1.0. 33 of the 38 units are entirely flat (no nesting at all), and the deepest nesting observed anywhere is 2 levels, in `Data.FileIO.Read`. Nothing here comes close to the depth-4 threshold this analyzer treats as a flattening priority.

**Hotspots.** None.

### NPath Complexity (#6) — structural

**What it is.** The number of distinct acyclic execution paths that actually exist through a unit — a different, faster-growing number than the paths cyclomatic complexity requires you to test.

**Why it matters here.** It's the gap between "we have full branch coverage" and "we tested the combinations."

**What we found.** Headline: "38 unit(s); worst NPath 16; 0 unit(s) beyond exhaustive path testing." Score 16.0, level **L1 (trivial)**. The worst unit — `Bank.Bank.withdraw` and `Data.FileIO.Read`, both at NPath 16 — needs at most 3.2 paths tested per branch-coverage test case, nowhere near the point where "branch-covered" and "combination-tested" diverge meaningfully. Every unit remains exhaustively testable. Confidence is 0.85: the report notes NPath assumes independent branches, so correlated conditions could make the true reachable path count lower than reported — this is an upper bound.

**Hotspots.** None.

### Runtime Complexity (#17) — structural

**What it is.** The expected cost of EXECUTING the code — its algorithmic growth class and the work it does per unit of input.

**Why it matters here.** None of the other metrics predict what happens as data volume grows; this one does.

**What we found.** Headline: "38 unit(s); 0 super-linear; 0 with I/O or SQL inside a loop; 1 recursive." Score 25.0, level **L3 (moderate)**, confidence 1.0 on the report as a whole. The growth-class distribution across the 38 units is 32 at O(1), 2 at O(n), 3 at "O(n) recursive," and 1 at O(2^n): the one exponential-flagged unit is an overload of `Bank.Bank.addAccount` that is both recursive and contains an unbounded loop calling itself — its item-level confidence is only 0.65 because the tree carries no `bounded` flag on that loop, so growth is inferred from nesting alone and may overstate a unit that is actually iterating a fixed-size structure. No unit anywhere performs I/O or SQL inside a loop.

**Hotspots.** None at the report level, though the recursive `Bank.Bank.addAccount` overloads (scores 20.4–25.0, level L3) are the items worth a second look per the analyzer's own item data.

### Data Flow Complexity (#12) — data

**What it is.** How values and data move across statements, functions and modules — the transformations, side effects and data dependencies that make code hard to reason about.

**Why it matters here.** This is where the codebase's biggest structural problem actually shows up.

**What we found.** Headline: "38 unit(s); max data-flow score 144.0; 11 shared data element(s); 9 data-heavy unit(s)." Score 144.0, level **L5 (severe)**, confidence 1.0. Nine units are flagged, all of them the GUI account-creation and transaction forms: `AddSavingsAccount` (144.0), `AddCurrentAccount` (141.0), `AddStudentAccount` (139.5), `WithdrawAcc` (132.0), `Menu` (114.0), `DepositAcc` (105.0), `Login.initialize` (95.5), `AddAccount` (75.0) and `DisplayList` (37.0) — every one of them at level L5. What drives the score is not branch count (these units are cyclomatically trivial) but a combination of shared data references and very high outbound call counts (up to 88 calls out of `AddSavingsAccount` alone) into the shared `Bank`/`FileIO` state. As the report's own interpretation notes: a unit reading data that other units also touch is coupled through state, not just through calls, and cannot be moved without moving that state too.

**Hotspots.** The same 9 units listed above, all L5 — this is the single strongest signal in the run.

### Coupling Complexity (#4) — coupling

**What it is.** How tightly units are bound to each other — what decides what can actually be extracted or moved.

**Why it matters here.** Every decomposition or service-extraction plan is a coupling argument.

**What we found.** Headline: "38 unit(s); 0 hub(s); 35 independently extractable; 10 isolated." Score 4.0, level **L1 (trivial)**, confidence 1.0. No unit is both heavily called and calls widely (a "hub"), 35 of 38 units are independently extractable by call-graph structure alone, and 10 units have no inbound or outbound calls at all. This is a low-coupling-at-the-call-graph-level codebase — which makes the data-flow finding above more notable, since coupling here hides in shared state rather than in the call graph.

**Hotspots.** None.

### Cohesion Complexity (#8) — coupling

**What it is.** How closely related the responsibilities inside a class are, measured via the LCOM family of metrics.

**Why it matters here.** Low cohesion signals a class doing too many unrelated things.

**What we found.** Headline: "21 type(s); worst LCOM4 2; 0 type(s) with low cohesion (>=3 components)." Score 2.0, level **L2 (low)**, confidence 1.0. The worst type is `Bank.SavingsAccount` with LCOM4 of 2 — meaning it could in principle be split into 2 independent method clusters — but that is well under the threshold (3+) this analyzer treats as a low-cohesion finding worth acting on.

**Hotspots.** None.

### Dependency Complexity (#9) — coupling

**What it is.** Internal, external, library, API, DB and platform dependencies of the codebase, read from the dependency graph.

**Why it matters here.** Dependencies are a major driver of migration effort and upgrade risk.

**What we found.** Headline: "50 module(s); 115 external dependency/ies; longest chain 3; 0 dependency cycle(s)." Score 45.7, level **L3 (moderate)**, confidence 1.0. Of 141 total dependency edges, 115 (82%) are external library dependencies — almost entirely Swing/AWT (`javax.swing.*`, `java.awt.*`) and `java.io.*` — versus only 26 internal ones. There are no dependency cycles, so nothing here blocks independent extraction on cyclicality grounds, but the ten hotspot modules (`GUI.WithdrawAcc` fan-out 18, `GUI.DepositAcc` fan-out 16, `GUI.Menu` fan-out 15, and six more, all at instability 1.0 except `Data.FileIO` at 0.462) are heavily dependent on the UI toolkit, which is exactly the kind of dependency a platform migration has to re-implement rather than translate mechanically.

**Hotspots.** `GUI.WithdrawAcc`, `GUI.DepositAcc`, `GUI.Menu`, `Data.FileIO`, `GUI.AddCurrentAccount`, `GUI.AddSavingsAccount`, `GUI.AddStudentAccount`, `GUI.DisplayList`, `GUI.AddAccount`, `GUI.Login` — ten modules, ranked by fan-out.

### Change Impact Complexity (#10) — coupling

**What it is.** How widely a change to one component can ripple through the system — its blast radius.

**Why it matters here.** It sizes the regression scope of a change before you make it.

**What we found.** Headline: "85 component(s); 0 high-impact; worst change reaches 10% of the system." Score 0.11, level **L2 (low)**, confidence 1.0. The widest blast radius belongs to shared UI primitives (`java.awt.Font`, `javax.swing.JFrame`, `javax.swing.JLabel`), each reaching 9 of 84 other components (10.7%) — meaning a change to one of those library touchpoints could plausibly require re-testing about a tenth of the system. No component crosses the 0.15 threshold this analyzer treats as high-impact.

**Hotspots.** `java.awt.Font`, `javax.swing.JFrame`, `javax.swing.JLabel` (impact ratio 0.107 each), plus `Bank.*`, `java.awt.event.ActionEvent`/`ActionListener`, and the `java.io.File*Stream`/`IOException`/`ObjectInputStream` family (impact ratio 0.095 each).

### Inheritance Complexity (#13) — coupling

**What it is.** Complexity introduced by inheritance hierarchies — DIT (depth) and NOC (number of children).

**Why it matters here.** Deep or wide inheritance makes behaviour hard to trace without reading the whole chain.

**What we found.** Headline: "21 type(s); max inheritance depth 2; widest base has 2 child(ren); 0 deep hierarchy(ies)." Score 2.0, level **L2 (low)**, confidence 1.0. `Bank.StudentAccount` sits at the deepest point in the hierarchy (DIT=2, extending `SavingsAccount`, which extends `BankAccount`); `BankAccount` itself is the widest base with 2 direct children (`CurrentAccount`, `SavingsAccount`). Nothing approaches the deep-hierarchy threshold.

**Hotspots.** None (the worst item, `Bank.StudentAccount`, sits at L2).

### Interface / API Complexity (#14) — coupling

**What it is.** Complexity of the interfaces, endpoints and contracts a system exposes — operation count, parameter breadth, schema count.

**Why it matters here.** A wide contract surface is costly to change and integrate against, though this matters less for a standalone desktop app than for a service-oriented one.

**What we found.** Headline: "34 exposed operation(s); avg 0.88 param(s)/op; 0 schema(s); 0 external API contract(s)." Score 36.2, level **L3 (moderate)**, confidence 1.0. There are no external API contracts and no schemas/DTOs — unsurprising for a single-process Swing application — and the average operation takes under one parameter. The widest operation, `Bank.Bank.addAccount`, takes 4 parameters, well within normal range.

**Hotspots.** None listed.

### Architectural Complexity (#20) — coupling

**What it is.** Structural quality of the system ABOVE the unit: module dependencies, layering, and decomposition seams.

**Why it matters here.** It answers whether the system can be decomposed at all, independent of how clean or messy individual units are.

**What we found.** Headline: "50 module(s); 0 dependency cycle(s) covering 0 module(s); 0 layering violation(s); 1 hub unit(s)." Score 7.2, level **L1 (trivial)**, confidence 0.9 (the `layers` optional input is absent, so layering violations specifically could not be checked — the caveat notes this explicitly). There are no dependency cycles and no modules in Martin's "zone of pain." One god unit is identified: `Bank.Bank.addAccount`, with fan-in 3, fan-out 7 and an information-flow score of 441 — the natural first seam to address if this codebase is ever decomposed, per the analyzer's own decomposition guidance.

**Hotspots.** None at the report level; `Bank.Bank.addAccount` is flagged as the sole god unit.

### Maintainability Complexity (#11) — composite

**What it is.** Overall difficulty of maintaining the code over time, combining size, cyclomatic complexity, Halstead volume and comment density into the industry Maintainability Index.

**Why it matters here.** This is the number a takeover or modernization assessment leads with.

**What we found.** Headline: "38 unit(s); LOC-weighted Maintainability Index 37.8/100; 12 hard-to-maintain unit(s)." Score 37.8, level **L5 (severe)**. The worst-scoring unit in the entire codebase is `GUI.AddStudentAccount.AddStudentAccount` at MI 28.3/100, followed closely by `GUI.Menu.Menu` (28.6), `GUI.AddCurrentAccount.AddCurrentAccount` (28.8) and `GUI.AddSavingsAccount.AddSavingsAccount` (29.4) — all four in the severe band, driven by large Halstead volume (each in the 4,000–5,000 range) on units with essentially zero comments. 12 of the 38 units fall below the "hard to maintain" bands. Confidence is 0.7: `halstead` is absent from the tree so volume was estimated from size and branching rather than measured directly, and `comment_lines` is absent so no comment-density bonus was applied — both push the reported MI lower than a fully-instrumented run might show, but the direction of the finding (large, comment-free GUI form classes are the maintenance burden) is unlikely to change.

**Hotspots.** Ten units at L4/L5: `AddStudentAccount` (28.3, L5), `Menu` (28.6, L5), `AddCurrentAccount` (28.8, L5), `AddSavingsAccount` (29.4, L5), `WithdrawAcc` (30.1, L4), `DepositAcc` (31.8, L4), `AddAccount` (35.5, L4), `Login.initialize` (36.9, L4), `Bank.Bank.display` (44.9, L4), `Data.FileIO.Read` (47.4, L4).

### Testability Complexity (#16) — composite

**What it is.** How hard it is to get a unit under test at all, separating test burden (paths to cover) from test friction (hidden inputs, side effects, missing seams).

**Why it matters here.** Modernization is only safe behind a characterization-test net, and this predicts whether that net can actually be built.

**What we found.** Headline: "38 unit(s); ~70 test case(s) for branch coverage; 4 unit(s) blocked or hostile to isolation." Score 24.0, level **L3 (moderate)**, confidence 1.0. Of 38 units, 34 are "tractable" (callable in isolation, cover the paths and move on) and 4 are "blocked" (few paths, but cannot be reached in isolation without introducing a seam first) — `Bank.BankAccount.BankAccount` (the constructor, score 24.0) and the three GUI account-creation constructors `AddCurrentAccount`, `AddSavingsAccount`, `AddStudentAccount` (score 21.5 each), all blocked by 4 hidden inputs not passed as parameters plus 4 writes to shared state that a test would need to reset. Separately, 24 of the 38 units have at least one hidden input, though most of those remain tractable rather than blocked.

**Hotspots.** None in the report's own `hotspots` field, but the 4 "blocked" items above (`BankAccount`, `AddCurrentAccount`, `AddSavingsAccount`, `AddStudentAccount`) are the ones the profile distinction is built to surface.

### Migration Complexity (#19) — composite

**What it is.** The effort and risk of moving this code to a different language, runtime or platform, scoring volume (how much there is to move) separately from blockers (what defeats automated translation) and mapping the result onto a migration strategy.

**Why it matters here.** This is the question a modernization programme is actually funded to answer, and every other analyzer feeds into it.

**What we found.** Headline: "38 unit(s); 1 require rearchitecture or rebuild; ~12% of the work is plausibly automatable; 0 translation blocker(s) found." Score 23.6, level **L3 (moderate)**. The strategy distribution across the 38 units is 28 rehostable (move as-is), 9 requiring refactor first, and 1 — `GUI.Menu.Menu` — requiring rearchitecture. No true translation blockers (dynamic SQL, platform calls, unstructured jumps) were found anywhere, so this is a codebase where the difficulty is size and shape, not un-translatable constructs. Confidence is 0.6, the lowest of any measured skill, because four optional inputs are entirely absent from the tree (`sql`, `platform_calls`, `dynamic_constructs`, `conditional_compilation`); more importantly, this composite depends on Database Complexity (#15) and Configuration Complexity (#18), and since neither of those ran, their contribution to this score was estimated from the tree rather than measured — the report's own caveat states this explicitly and recommends re-running with the full input set for a costing-grade figure.

**Hotspots.** `GUI.Menu.Menu` (score 23.6, L3, recommended strategy "rearchitect"), then a cluster of refactor-strategy GUI units: `GUI.WithdrawAcc.WithdrawAcc` (21.8), `GUI.DepositAcc.DepositAcc` (21.5), `GUI.AddCurrentAccount.AddCurrentAccount` (20.8), `GUI.AddStudentAccount.AddStudentAccount` (19.4), `GUI.AddSavingsAccount.AddSavingsAccount` (19.2), `GUI.AddAccount.AddAccount` (18.0), `GUI.DisplayList.DisplayList` (17.1), `GUI.Login.Login` (13.6) and `GUI.Login.initialize` (15.1).

## Skills not measured

**Database Complexity (#15).** This skill would score how hard the code's relationship with persistent data is to understand, change and migrate — SQL surface, schema reach, statement shape, dynamic SQL and transaction control, plus access-pattern penalties like SQL inside a loop. It did not run because the tree carries none of `sql`, `cursors` or `transactions` — the analyzer requires at least one. This codebase does read/write account data via `Data.FileIO` (Java object serialization, not SQL), so the gap here may be a legitimate absence of a database rather than a parser defect, but it cannot be distinguished from a parser gap without the parser emitting those fields (even as empty arrays) to confirm it looked.

**Configuration Complexity (#18).** This skill would score how much of the system's behaviour is decided outside the source code — config keys, environment variables, feature flags, conditional compilation, and hardcoded literals that should be config. It did not run because the tree carries none of `config_reads`, `literals`, `conditional_compilation` or `feature_flags` — the analyzer requires at least one. Whoever owns the Java parser should confirm whether this reflects a genuine absence of externalized configuration in this codebase, or whether the parser simply does not yet extract literal/config-read signals from Java source.

## Closing summary

Overall level is **L5 (severe)**, driven by two concrete findings rather than an averaging artifact: Data Flow Complexity (#12, score 144.0) shows nine GUI form units bound to shared `Bank`/`FileIO` state through heavy outbound calls, and Maintainability Complexity (#11, score 37.8/100) shows the same units — large, comment-free Swing form classes — are the hardest in the codebase to maintain. These nine units (`AddAccount`, `AddCurrentAccount`, `AddSavingsAccount`, `AddStudentAccount`, `DepositAcc`, `DisplayList`, `Login.initialize`, `Menu`, `WithdrawAcc`) are the run's corroborated hotspots, each flagged independently by both skills. Everything structural (cyclomatic, cognitive, nesting, NPath, control flow) is trivial-to-low, so the difficulty here is not that the logic is hard to follow — it's that state is shared and undocumented. Coverage is 18 of 20 skills (90%); Database Complexity and Configuration Complexity did not run because the tree carries none of their required fields, so this read of the codebase does not yet account for whatever SQL/schema or configuration surface may exist.
