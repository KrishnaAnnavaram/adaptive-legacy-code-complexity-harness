# Target-Fit Report — Java → C++ — D:/adaptive-legacy-code-complexity-harness/samples/java_bank

## Table of contents

1. [About this report — read this first](#about-this-report--read-this-first)
2. [Descriptor status: unreviewed](#descriptor-status-unreviewed)
3. [About this codebase](#about-this-codebase)
4. [About the target: C++](#about-the-target-c)
5. [From Normalized Tree to Projected Tree](#from-normalized-tree-to-projected-tree)
6. [Overall complexity score — target vs. source](#overall-complexity-score--target-vs-source)
7. [Coverage: 17 of 20 measured](#coverage-17-of-20-measured)
8. [Per-complexity deep dive](#per-complexity-deep-dive)
   - [07 Structural Complexity](#07-structural-complexity)
   - [01 Cyclomatic Complexity](#01-cyclomatic-complexity)
   - [02 Cognitive Complexity](#02-cognitive-complexity)
   - [03 Control Flow Complexity](#03-control-flow-complexity)
   - [05 Nesting Complexity](#05-nesting-complexity)
   - [06 NPath Complexity](#06-npath-complexity)
   - [17 Runtime Complexity](#17-runtime-complexity)
   - [12 Data Flow Complexity](#12-data-flow-complexity)
   - [04 Coupling Complexity](#04-coupling-complexity)
   - [08 Cohesion Complexity](#08-cohesion-complexity)
   - [09 Dependency Complexity](#09-dependency-complexity)
   - [10 Change Impact Complexity](#10-change-impact-complexity)
   - [13 Inheritance Complexity](#13-inheritance-complexity)
   - [14 Interface / API Complexity](#14-interface--api-complexity)
   - [20 Architectural Complexity](#20-architectural-complexity)
   - [11 Maintainability Complexity](#11-maintainability-complexity)
   - [16 Testability Complexity](#16-testability-complexity)
   - [19 Migration Complexity](#19-migration-complexity)
   - [15 Database Complexity](#15-database-complexity)
   - [18 Configuration Complexity](#18-configuration-complexity)
9. [C++'s goto support: a real capability difference that this codebase never exercises](#c-goto-support-a-real-capability-difference-that-this-codebase-never-exercises)
10. [The one sharp edge: Migration Complexity's score moved for a reason that isn't "C++ is easier"](#the-one-sharp-edge-migration-complexitys-score-moved-for-a-reason-that-isnt-c-is-easier)
11. [Conclusion and recommended next steps](#conclusion-and-recommended-next-steps)

---

## About this report — read this first

**This document is built from real, independently-computed target-side
complexity scores, not from carried-over or reweighted source numbers.**
Every score below in the [per-complexity deep dive](#per-complexity-deep-dive)
came from actually re-running the same 20 analyzer scripts in
`.claude/complexities/` — the identical modules Agent 3 uses, invoked a
second time via `.claude/complexities/run_pipeline.py`'s own `discover()`,
`order()`, `execute()` and `consolidate()` functions — against a **second,
projected tree** built specifically to represent what a faithful Java→C++
translation's shape would honestly be. Agent 3's original
`complexity_artifact.json` (the Java/source-side result) is read only
afterward, to build the `comparison` section quoted throughout this report
for context. It is never the source of any number that appears as a
"target" value here.

Concretely, this run did three things, in order:

1. **Projected** `outputs/java_bank/normalized_tree.json` onto C++'s
   capability descriptor, producing a second Normalized Tree (never written
   to disk as its own file, but fully described by the `projection` block of
   this run's own `complexity_artifact.json`).
2. **Ran** all 20 complexity analyzers against that projected tree, exactly
   as Agent 3 runs them against the original — same code, same gating rules,
   same envelope.
3. **Compared** the fresh target-side results against Agent 3's own finished
   source-side artifact, purely for traceability — never as an input to any
   target score.

Every number in this report traces to one of exactly two places:
`outputs/java_bank/target/cpp/complexity_artifact.json` (this run's own
artifact and its `reports/`) for every "target" figure, or
`outputs/java_bank/complexity_artifact.json` and its `reports/` (Agent 3's
finished, unmodified output) for every "source" figure quoted for
comparison. Nothing here was estimated, guessed, or backfilled by this
report's author.

---

## Descriptor status: unreviewed

The C++ capability descriptor used for this run —
`.claude/target_fit/languages/cpp.json` — carries `"reviewed": false` and
`"source": "drafted"`. It was drafted this session and has not yet been
checked field-by-field by a maintainer against real C++ documentation. Its
own `notes` field says so directly: *"Drafted from general knowledge of the
language, not yet checked by a project maintainer... Verify every field
before treating target-fit findings derived from this file as final."*

This run's artifact reflects that directly: `descriptor_reviewed: false`,
`descriptor_source: "drafted"`, and the artifact-level `confidence.score` is
**0.6**, with the single stated reason: *"target descriptor for 'cpp' has
not been human-reviewed yet ... every score in this artifact is
provisional."* Treat every score in this report as provisional in that same
sense — genuinely computed, not guessed, but resting on a descriptor a
person has not yet checked field by field.

---

## About this codebase

Unchanged from Agent 3's own source-side report, because this run reads the
same upstream tree:

| Fact | Value | Source |
|---|---|---|
| Source language | Java | `normalized_tree.json` `language` |
| Target language | C++ | this run's `target_language` |
| Units (methods/constructors) | 36 | `normalized_tree.json` `units`; confirmed unchanged in `projection.units_projected` |
| Types | 12 | `normalized_tree.json` `types` |
| Source file / sample | `D:/adaptive-legacy-code-complexity-harness/samples/java_bank` | both artifacts' `source_file` |

See Agent 3's own `outputs/java_bank/complexity_report.md` for the full
domain-model description (a compact core-banking sample: accounts, a
savings-account subtype, transfers, interest accrual, audit logging). That
description does not change with target language and is not repeated here.

---

## About the target: C++

Everything below comes from `.claude/target_fit/languages/cpp.json`
directly — no field here is inferred or assumed beyond what the descriptor
states, and the descriptor itself is unreviewed (see above).

| Descriptor field | Value |
|---|---|
| Paradigm | multi-paradigm — procedural, object-oriented, generic; compiled to native machine code |
| `structured_control_flow_only` | **false** |
| `supports_goto` | **true** — genuine, inherited from C |
| `supports_alter_style_dynamic_jump` | false |
| Typing | static |
| Garbage collected | false (manual memory management) |
| Numeric model | no native arbitrary-precision/fixed-point decimal type; exact-precision arithmetic requires a library (e.g. Boost.Multiprecision) or a hand-written fixed-point type |
| Exception model | exceptions (try/catch/throw); commonly disabled entirely in embedded/performance-critical code, reverting error signaling to return codes |
| Concurrency model | native OS threads (`std::thread`, C++11+); no GIL; manual synchronization via mutexes/atomics |
| Native screen I/O | false |
| Native SQL access | none in the standard library; requires a third-party driver (e.g. libpqxx, SOCI, ODBC) |
| `multiple_inheritance` | **true** — native multiple inheritance, including virtual inheritance to resolve diamond-shaped hierarchies |

Two fields matter most for this run's projection:

- `multiple_inheritance` is not `null`, so C++ is treated as having a real
  object model, and `types` is **not** dropped from the projected tree.
- `supports_goto` is **true** — unlike both Java's and Python's descriptors
  (both `false`), C++ genuinely supports `goto`, a real capability
  difference inherited from C, even though idiomatic modern C++ discourages
  its use. This is the one descriptor field in this run that is
  qualitatively different from every other target run against this
  codebase so far — see the [dedicated section](#c-goto-support-a-real-capability-difference-that-this-codebase-never-exercises)
  below for what that does and does not change here.

---

## From Normalized Tree to Projected Tree

`.claude/target_fit/project_tree.py` applies exactly three generic,
descriptor-driven rules. Here is what each one actually did for this
specific tree, per this run's own `projection` block:

**Rule 1 — jump constructs.** Any unit whose CFG contains `GOTO`, `ALTER`,
`PERFORM_THRU` or `FALL_THROUGH` is dropped only if the target's descriptor
says it can't express that construct. C++'s descriptor declares
`supports_goto: true` and `supports_alter_style_dynamic_jump: false` — so
even a unit containing a real `GOTO` would have survived this rule for a
C++ target (unlike the Python/Java runs against this same tree, where
`supports_goto: false` would have dropped it). In practice, for this
codebase, **the rule removed nothing regardless**: `projection.units_dropped`
is an empty list, and `projection.units_projected` (36) equals
`projection.units_total_source` (36). This is corroborated independently by
Control Flow Complexity's own target-side metrics (`total_jumps: 0`,
`units_with_alter: 0`, `fully_structured_units: 36`) — this Java codebase
simply contains no `GOTO`/`ALTER`/`PERFORM_THRU`/`FALL_THROUGH` constructs to
begin with, so neither C++'s support for `goto` nor a hypothetical target's
lack of it ever came into play here. All 36 units survived projection
unit-for-unit.

**Rule 2 — object model.** `types` is dropped entirely only if the target's
`multiple_inheritance` is `null`. C++'s is `true`, so `types` was **carried
through unchanged** — `projection.object_model_dropped: false`,
`object_model_dropped_reason: null`. This is why Cohesion Complexity (#8) and
Inheritance Complexity (#13), both of which require `types`, ran to
completion in this run rather than gating.

**Rule 3 — volume fields.** `loc`, `comment_lines` and `halstead` were
stripped from every one of the 36 surviving units, unconditionally — this
happens for every target, always, per
`projection.fields_stripped_every_unit`. The stated reason:
*"loc/comment_lines/halstead describe the volume of source-language text;
projecting them onto a target without real target code would require an
invented verbosity ratio, which this design refuses to do."* This is the
rule with the most consequences below — it is why Maintainability
Complexity gates outright, why Structural/Cyclomatic/Cognitive run with
slightly reduced confidence, and why Migration Complexity's score moved
(see the [dedicated section](#the-one-sharp-edge-migration-complexitys-score-moved-for-a-reason-that-isnt-c-is-easier)
below). `start_line`/`end_line` per unit are **not** in the stripped set,
which is why Structural Complexity was still able to derive an equivalent
size figure for each unit from its line range rather than losing the signal
entirely.

Net effect for this run: **36/36 units projected, 0 dropped, `types`
retained, three volume fields stripped from every unit.**

---

## Overall complexity score — target vs. source

**Target worst-case level: L3 (moderate)** — identical to source. The same
skills that reached L3 on the Java side (Runtime, Data Flow, Coupling,
Cohesion, Interface/API, Testability) reach L3 again here, because none of
projection's three rules touched the tree fields those skills actually read
(`cfg`, `call_graph`, `dependency_graph`, `types`, `references`, `writes`).

**Target mean level: 1.88** (`overall.mean_level`), against source's 1.94.
This is *not* evidence C++ is "easier" in general — it moved because one
fewer skill measured this run (17 vs. 18; see
[coverage](#coverage-17-of-20-measured)), and the skill that stopped
measuring (Maintainability) was itself a mid-severity L3 finding on the
source side, so removing it from the denominator nudges the mean down
mechanically. It is a coverage artifact, not a claim about C++'s
maintainability.

**Mean confidence across reports (`reports[]`): 0.92** — arithmetically the
same figure as the earlier Python-target run against this tree, for the same
reason: the same handful of skills (Structural, Cyclomatic, Cognitive) have
their own optional-input confidence discount now naming `loc` as missing,
regardless of which target descriptor is in play, because Rule 3 (volume
fields stripped) is applied identically to every target.

**Artifact-level confidence: 0.6** — this is the separate,
descriptor-driven number described in
[Descriptor status](#descriptor-status-unreviewed) above; do not confuse it
with the 0.92 mean-of-reports figure.

---

## Coverage: 17 of 20 measured

Target-side coverage (`coverage` block of this run's artifact):
`analyzers_ok: 17`, `analyzers_insufficient_input: 3`, `analyzers_error: 0`,
`completeness: 0.85` — one skill fewer than source's 18/20 (90%). The three
gated skills, and why, in this run:

| Skill | Gated on | Same as source? |
|---|---|---|
| 15 Database Complexity | none of `sql`/`cursors`/`transactions` present | Yes — this codebase never carried these fields, in either tree |
| 18 Configuration Complexity | none of `config_reads`/`literals`/`conditional_compilation`/`feature_flags` present | Yes — same reason, unaffected by projection |
| 11 Maintainability Complexity | required `loc` absent | **No — new this run.** Source-side Maintainability ran (`ok`, L3, score 68.0); target-side gates outright because `loc` is stripped from every unit by projection Rule 3, and Maintainability declares `loc` a required input, not merely optional |

The net drop from 18/20 to 17/20 is entirely attributable to Rule 3 (volume
fields stripped) intersecting with Maintainability's `requires: loc` — the
same central gating mechanism (`Tree.require(spec)` in `_core.py`) that
every analyzer already uses, firing correctly on a field this projection
was always going to remove, independent of which target language is chosen.

---

## Per-complexity deep dive

Every entry below states this run's own target-side status/score/level/
confidence first, then the source-side number for comparison — always
labelled as a comparison, never presented as the mechanism. All figures
below are traced directly to
`outputs/java_bank/target/cpp/reports/NN_*.json` (target) and
`outputs/java_bank/reports/NN_*.json` /
`outputs/java_bank/complexity_artifact.json` (source).

### 07 Structural Complexity

**Target result.** Status `ok`, score **0.23**, level **L1 (trivial)**,
confidence **0.85**. `inputs_used`: `units`, `cfg`. `inputs_missing_optional`:
`loc`, `comment_lines` (both). Headline: *"36 unit(s), 185 line(s); top 3
unit(s) hold 23% of the code; 3 outlier(s)."*

**Units dropped for this metric.** None — `projection.units_dropped` is
empty, so all 36 units this skill scores are the same 36 units source
scored.

**Why the score didn't move despite `loc` being stripped.** This skill
declares `loc` merely *optional*. With the declared field gone, it fell back
to deriving each unit's size from `start_line`/`end_line` — fields the
volume-stripping rule does **not** remove — which for this codebase
reproduces the same line-range figures as the original `loc` values almost
exactly (`total_loc`: 185 here vs. 184 on the source side, a rounding
artifact of the line-range derivation, not a different codebase). Every one
of this skill's own top-outlier units (`Bank.transfer` at 16,
`TransactionLog.linked` at 15, `Bank.describe` at 12,
`AccountType.forBalance` and `CompoundInterestPolicy.monthsToReach` at 9
each, `TransactionLog.totalFor` at 9) matches the source-side deep dive
line-for-line.

**Comparison.** Source: `ok`, 0.23, L1, confidence 0.85 (missing only
`comment_lines`, since `loc` was present there). Target confidence carries
the same numeric value but for a different, more complete reason — both
`loc` and `comment_lines` are now named as missing, even though the score
itself is unaffected.

---

### 01 Cyclomatic Complexity

**Target result.** Status `ok`, score **4.0**, level **L1 (trivial)**,
confidence **0.9**. `inputs_used`: `units`, `cfg`. `inputs_missing_optional`:
`loc`. Headline: *"36 unit(s); max v(G) 4; 56 test case(s) needed for
branch coverage; 0 unit(s) above threshold."* Per-unit v(G) values are
byte-identical to source (`Bank.transfer` and `TransactionLog.totalFor`
both at 4, the ceiling; 56 total test cases for full branch coverage).

**Units dropped for this metric.** None.

**Comparison.** Source: `ok`, 4.0, L1, confidence **1.0**. The score and
level are identical — cyclomatic counting never touches `loc` — but
confidence dropped from 1.0 to 0.9 purely because `loc` is now absent and
this skill lists it as an optional input it would have liked to have. This
is a confidence-only difference with no scoring consequence.

---

### 02 Cognitive Complexity

**Target result.** Status `ok`, score **4.0**, level **L1 (trivial)**,
confidence **0.9**. `inputs_used`: `units`, `cfg`. `inputs_missing_optional`:
`loc`. Headline: *"36 unit(s); max cognitive 4; 0 unit(s) hard because of
NESTING rather than branch count."* `max_gap_vs_cyclomatic: 0`, matching
source exactly — difficulty in this codebase is driven by branch count, not
nesting, regardless of target language. `TransactionLog.totalFor` remains
the single most cognitively-loaded unit (cognitive 4, matching its
cyclomatic score).

**Units dropped for this metric.** None.

**Comparison.** Source: `ok`, 4.0, L1, confidence **1.0**. Same pattern as
Cyclomatic — score and level unchanged, confidence dropped from 1.0 to 0.9
solely because `loc` (optional here too) is now absent.

---

### 03 Control Flow Complexity

**Target result.** Status `ok`, score **1.0**, level **L2 (low)**,
confidence **0.8**. `inputs_used`: `units`, `cfg`. `inputs_missing_optional`:
none. Headline: *"36/36 unit(s) fully structured; 0 not mechanically
translatable; 0 contain ALTER."* `total_jumps: 0`, `units_with_alter: 0`,
`fully_structured_units: 36`, `structured_ratio: 1.0` — every one of the 36
projected units remains fully structured. `Bank.transfer` is again the sole
unit at L2 (`unstructuredness_index: 1.0`, reason: "3 exit points"), exactly
as on the source side.

**Units dropped for this metric.** None — and this is the metric most
directly relevant to Rule 1 (jump constructs), and the one where C++'s
descriptor is qualitatively different from every other target run against
this tree. C++'s descriptor declares `supports_goto: true` (unlike Java's
and Python's, both `false`), meaning a unit containing a real `GOTO` would
have survived projection for a C++ target where it would have been dropped
for a Python target. That difference simply never gets exercised here:
this codebase's own CFGs contain zero jump nodes of any kind
(`jumps_by_kind: {}` on every one of the 36 items), so no unit's survival or
removal in this run depended on C++'s goto support one way or the other.
See the [dedicated section](#c-goto-support-a-real-capability-difference-that-this-codebase-never-exercises)
below.

**Comparison.** Source: `ok`, 1.0, L2, confidence **0.8** — identical in
every respect, including the confidence reason (this skill's confidence
discount is about its own methodology — an unstructuredness-index proxy
rather than true McCabe ev(G) — not about `loc`, so it is unaffected by
volume-field stripping).

---

### 05 Nesting Complexity

**Target result.** Status `ok`, score **2.0**, level **L1 (trivial)**,
confidence **1.0**. `inputs_used`: `units`, `cfg`. No missing optional
inputs. Headline: *"36 unit(s); deepest nesting 2; 0 unit(s) at depth >= 4;
31 flat."* `TransactionLog.totalFor` remains the single deepest unit
(depth 2, an `OR` at line 21), matching source exactly.

**Units dropped for this metric.** None.

**Comparison.** Source: `ok`, 2.0, L1, confidence **1.0** — no difference
at all. Nesting Complexity never declares `loc` as an input of any kind, so
volume-field stripping has zero effect on it.

---

### 06 NPath Complexity

**Target result.** Status `ok`, score **8.0**, level **L1 (trivial)**,
confidence **0.85**. `inputs_used`: `units`, `cfg`. No missing optional
inputs. Headline: *"36 unit(s); worst NPath 8; 0 unit(s) beyond exhaustive
path testing."* `Bank.transfer` and `TransactionLog.totalFor` remain tied
at NPath 8, `paths_per_branch_test` maxing at 2.0 — identical to source.

**Units dropped for this metric.** None.

**Comparison.** Source: `ok`, 8.0, L1, confidence **0.85** — no difference.
This skill's confidence discount is about the independent-branches
assumption inherent to NPath counting, not about `loc`, so it is unaffected.

---

### 17 Runtime Complexity

**Target result.** Status `ok`, score **20.2**, level **L3 (moderate)**,
confidence **1.0** at the skill level (`mean_confidence` across items:
0.76). `inputs_used`: `units`, `cfg`, `call_graph`. Headline: *"36 unit(s);
0 super-linear; 0 with I/O or SQL inside a loop; 1 recursive."* Growth
distribution identical to source: 30 units O(1), 5 units O(n), 1 unit
"O(n) recursive." `CompoundInterestPolicy.rate` is again the unit setting
this skill's L3 ceiling, flagged with the same reason as source:
*"recursive - termination and depth need explicit review."*

**Units dropped for this metric.** None. Runtime Complexity reads `cfg` and
`call_graph`, neither touched by any of the three projection rules for this
codebase.

**Comparison.** Source: `ok`, 20.2, L3, confidence 1.0 — identical in every
figure, including which specific unit drives the score and every per-item
confidence discount (the O(n) units without a `bounded` loop flag carry the
same 0.65 per-item confidence in both runs).

---

### 12 Data Flow Complexity

**Target result.** Status `ok`, score **16.0**, level **L3 (moderate)**,
confidence **1.0**. `inputs_used`: `units`, `cfg`. Headline: *"36 unit(s);
max data-flow score 16.0; 10 shared data element(s); 0 data-heavy unit(s)."*
`Bank.transfer` remains the ceiling item (fan-out to 8 downstream calls),
and the same 10 of 16 data elements remain shared across units — `Account`
(per-module score 43.0) and `Bank` (33.5) remain the most state-entangled
modules.

**Units dropped for this metric.** None.

**Comparison.** Source: `ok`, 16.0, L3, confidence 1.0 — identical.

---

### 04 Coupling Complexity

**Target result.** Status `ok`, score **36.0**, level **L3 (moderate)**,
confidence **1.0**. `inputs_used`: `units`, `call_graph`, `dependency_graph`.
Headline: *"36 unit(s); 0 hub(s); 33 independently extractable; 15
isolated."* `Account.withdraw` remains the ceiling item at information-flow
score `(2×3)² = 36`; `Account.audit` and `Money.Money`'s constructor remain
flagged "utility," `Bank.transfer` remains the sole "orchestrator."

**Units dropped for this metric.** None.

**Comparison.** Source: `ok`, 36.0, L3, confidence 1.0 — identical.

---

### 08 Cohesion Complexity

**Target result.** Status `ok`, score **3.0**, level **L3 (moderate)**,
confidence **1.0**. `inputs_used`: `units`, `types`. Headline: *"12 type(s);
worst LCOM4 3; 2 type(s) with low cohesion (>=3 components)."* `Bank` and
`util.Validation` remain the two LCOM4-3 hotspots, with identical field/
method/shared-pair counts to the source run.

**Units dropped for this metric.** None. This is the metric that most
directly exercises projection Rule 2 (object model): it requires `types`,
which C++'s descriptor (native multiple inheritance, including virtual
inheritance for diamond hierarchies) allows to survive intact. Had the
target been a language whose descriptor declares `multiple_inheritance:
null` (e.g. COBOL or PL/SQL), this skill would have gated to
`insufficient_input` instead.

**Comparison.** Source: `ok`, 3.0, L3, confidence 1.0 — identical.

---

### 09 Dependency Complexity

**Target result.** Status `ok`, score **29.6**, level **L2 (low)**,
confidence **1.0**. `inputs_used`: `dependency_graph`. Headline: *"16
module(s); 6 external dependency/ies; longest chain 2; 0 dependency
cycle(s)."* Same 10 total dependency edges (6 library, 4 internal), same
zero cycles, same longest chain of 2 hops.

**Units dropped for this metric.** None (this skill scores modules, not
units, and the dependency graph is one of the fields projection carries
through unchanged for every target).

**Comparison.** Source: `ok`, 29.6, L2, confidence 1.0 — identical.

---

### 10 Change Impact Complexity

**Target result.** Status `ok`, score **0.1**, level **L2 (low)**,
confidence **1.0**. `inputs_used`: `call_graph`, `dependency_graph`, `units`.
Headline: *"52 component(s); 0 high-impact; worst change reaches 9% of the
system."* `Account.audit` remains the worst blast radius
(`impact_ratio: 0.098`), same as source.

**Units dropped for this metric.** None.

**Comparison.** Source: `ok`, 0.1, L2, confidence 1.0 — identical.

---

### 13 Inheritance Complexity

**Target result.** Status `ok`, score **1.0**, level **L1 (trivial)**,
confidence **1.0**. `inputs_used`: `types`. Headline: *"12 type(s); max
inheritance depth 1; widest base has 1 child(ren); 0 deep hierarchy(ies)."*
`SavingsAccount extends Account` remains the only inheritance relationship,
DIT 1, NOC 1 — no unit in this codebase uses multiple inheritance to begin
with, so C++'s native support for it (unlike this codebase's actual shape)
makes no measurable difference here.

**Units dropped for this metric.** None — `types` survived projection
because C++ declares a real object model (see Rule 2 above).

**Comparison.** Source: `ok`, 1.0, L1, confidence 1.0 — identical.

---

### 14 Interface / API Complexity

**Target result.** Status `ok`, score **35.8**, level **L3 (moderate)**,
confidence **1.0**. `inputs_used`: `units`, `meta`, `dependency_graph`.
Headline: *"33 exposed operation(s); avg 1.12 param(s)/op; 0 schema(s); 0
external API contract(s)."* `SavingsAccount`'s constructor remains the
heaviest single operation (4 parameters).

**Units dropped for this metric.** None.

**Comparison.** Source: `ok`, 35.8, L3, confidence 1.0 — identical. This
skill does not read `loc`, so volume-field stripping does not touch it at
all.

---

### 20 Architectural Complexity

**Target result.** Status `ok`, score **0.9**, level **L1 (trivial)**,
confidence **0.9**. `inputs_used`: `dependency_graph`, `types`, `call_graph`,
`units`. `inputs_missing_optional`: `layers`. Headline: *"16 module(s); 0
dependency cycle(s) covering 0 module(s); 0 layering violation(s); 0 hub
unit(s)."* Same caveat as source: *"No layer declaration - layering
violations not checked."*

**Units dropped for this metric.** None.

**Comparison.** Source: `ok`, 0.9, L1, confidence 0.9 — identical, including
the identical confidence reason (missing `layers`, which was never present
in the source tree either and is unrelated to projection).

---

### 11 Maintainability Complexity

**Target result.** Status **`insufficient_input`**. `level: null`,
`score: null`. `inputs_missing_required: ["loc"]`. Confidence **0.0**,
reason: *"required input absent."* Headline: *"NOT MEASURED - tree does not
carry required input(s): loc. Maintainability Complexity needs them to
produce a meaningful score; returning a zero here would be indistinguishable
from a clean result."*

**Units dropped for this metric.** N/A — this is not a per-unit drop; the
skill gated entirely before scoring any unit, because it declares `loc` a
*required* (not optional) input, and projection Rule 3 strips `loc` from
every unit unconditionally, for every target — C++ is not an exception.

**Comparison.** Source: `ok`, score **68.0**, level **L3 (moderate)**,
confidence 0.7 (`Bank.transfer` was the worst unit at MI 54.3). This is the
one genuine coverage change in this run relative to source — not a milder
finding, but the complete absence of one. See
[Coverage](#coverage-17-of-20-measured) above: this is exactly the outcome
the projection contract predicts for a field declared *required* rather
than merely *optional* (contrast with Migration Complexity below, which
declares the same field merely optional and therefore still runs).

---

### 16 Testability Complexity

**Target result.** Status `ok`, score **19.0**, level **L3 (moderate)**,
confidence **1.0**. `inputs_used`: `units`, `cfg`, `references`, `globals`,
`writes`, `call_graph`, `dependency_graph`, `meta`. Headline: *"36 unit(s);
~56 test case(s) for branch coverage; 0 unit(s) blocked or hostile to
isolation."* `Account`'s constructor remains the L3 ceiling item (test
friction 18.5: 3 hidden inputs, 3 shared-state writes), with
`TransactionLog$Entry`'s constructor close behind (friction 16.5) — both
byte-identical to source. 26 of 36 units still carry at least one hidden
input.

**Units dropped for this metric.** None. This skill does not read `loc` at
all, so it is entirely unaffected by volume-field stripping.

**Comparison.** Source: `ok`, 19.0, L3, confidence 1.0 — identical.

---

### 19 Migration Complexity

**Target result.** Status `ok`, score **3.8**, level **L1 (trivial)**,
confidence **0.5**. `inputs_used`: `units`, `cfg`, `dependency_graph`.
`inputs_missing_optional`: `sql`, `platform_calls`, `dynamic_constructs`,
`conditional_compilation`, **`loc`**. Headline: *"36 unit(s); 0 require
rearchitecture or rebuild; ~10% of the work is plausibly automatable; 0
translation blocker(s) found."* Every one of the 36 units is still
recommended `rehost` (100% rehost, `strategy_distribution`), zero blockers
found anywhere (`blocker_breakdown: {}`, every item's own `blockers: []`,
`total_blocker_score: 42.0`, `total_volume_score: 4.7`, `total_loc: 0`).

**Units dropped for this metric.** None.

**Comparison and the caveat that matters here.** Source: `ok`, score
**4.1**, level L1, confidence 0.6. The level did not change (both L1), but
the score moved from 4.1 to 3.8, and confidence dropped further (0.6 to
0.5) with `loc` newly named among the missing optional inputs. **This
delta is explained in full, with numbers, in the
[dedicated section](#the-one-sharp-edge-migration-complexitys-score-moved-for-a-reason-that-isnt-c-is-easier)
below** — in short, it is not a real reduction in C++ migration effort, and
must not be read as one. The numbers here are its own — verified against
`outputs/java_bank/target/cpp/reports/19_migration_complexity.json` directly
rather than assumed to match the earlier Python run — and they turn out to
be identical (3.8 vs. 4.1, confidence 0.5 vs. 0.6), because this analyzer's
own scoring code is target-language-agnostic: it reacts only to which
fields the tree carries, not to which `target_language` string is stamped on
the report, so a `loc`-stripped tree produces the same volume-score collapse
whichever target descriptor caused the stripping.

---

### 15 Database Complexity

**Target result.** Status `insufficient_input`. `level: null`,
`score: null`, confidence **0.0**, reason: *"required input absent."*
`status_reason`: *"tree carries none of: sql, cursors, transactions.
Database Complexity needs at least one of them; returning a zero here
would be indistinguishable from a clean result."*

**Units dropped for this metric.** N/A.

**Comparison.** Source: also `insufficient_input`, identical reason. This
codebase never carried `sql`/`cursors`/`transactions` in the original Java
tree either — projection changed nothing here, because there was nothing
for any of the three projection rules to touch (this gate is about
`requires_any`, not about volume fields or jump constructs or the object
model).

---

### 18 Configuration Complexity

**Target result.** Status `insufficient_input`. `level: null`,
`score: null`, confidence **0.0**, reason: *"required input absent."*
`status_reason`: *"tree carries none of: config_reads, literals,
conditional_compilation, feature_flags. Configuration Complexity needs at
least one of them; returning a zero here would be indistinguishable from a
clean result."*

**Units dropped for this metric.** N/A.

**Comparison.** Source: also `insufficient_input`, identical reason and
identical fields named. Same situation as Database Complexity — unaffected
by projection because the fields it needs were never present in either
tree.

---

## C++'s goto support: a real capability difference that this codebase never exercises

This is the one descriptor field worth calling out on its own for a C++
target, because it is qualitatively different from every other target run
against `java_bank` so far. Both Java's and Python's descriptors declare
`supports_goto: false`. C++'s descriptor declares `supports_goto: true` —
and this is a genuine capability fact, not an oversight: C++ inherited
`goto` from C, and the language standard has never removed it, even though
idiomatic modern C++ treats it as something to avoid in ordinary code.

Mechanically, this means projection Rule 1 behaves differently *in
principle* for a C++ target than it did for the Python-target run against
this same tree: a unit whose CFG contained a `GOTO` node would have been
**dropped** under Python's descriptor (which cannot express it) but
**kept** under C++'s descriptor (which can).

**For this specific codebase, that difference never actually fires.**
`projection.units_dropped` is empty in this run, exactly as it was for
Python, Java, and every other target run against this tree — not because
C++'s goto support made a difference, but because there is nothing here for
either capability to act on. Control Flow Complexity's own target-side
metrics confirm this directly: every one of the 36 items in
`outputs/java_bank/target/cpp/reports/03_control_flow_complexity.json`
reports `"jumps_by_kind": {}` and `"total_jumps": 0`, and the summary metrics
report `total_jumps: 0`, `units_with_alter: 0`, `fully_structured_units: 36`.
This Java codebase was written entirely with structured control flow to
begin with (if/else, for, while, switch, try/catch) — it contains zero
`GOTO`, `ALTER`, `PERFORM_THRU` or `FALL_THROUGH` constructs of any kind, so
neither target's ability nor inability to express them was ever put to the
test.

**The honest takeaway:** the target-fit mechanism here is genuinely
target-aware — it would produce a different projected tree, and likely a
different Control Flow Complexity finding, for a codebase that actually used
unstructured jumps (a hypothetical COBOL-style tree with real `GOTO`
statements, for instance, would keep those units for a C++ target while
dropping them for a Python target). For `java_bank`, C++'s `goto` support is
a fact worth recording about the descriptor, not a finding about this run —
it is a moot point for this particular codebase, and this report treats it
as exactly that rather than inflating it into evidence C++ is somehow a
"safer" target than Python for this tree.

---

## The one sharp edge: Migration Complexity's score moved for a reason that isn't "C++ is easier"

Migration Complexity's target score (**3.8**) is genuinely lower than its
source baseline (**4.1**) in this run's `comparison` section — the same
numeric delta seen in the earlier Python-target run against this tree. Read
on its own, that looks like "C++ needs slightly less migration effort than
staying in Java" — **that reading is wrong here for exactly the same reason
it was wrong for Python, and this section exists to correct it explicitly.**

The real mechanism, traceable entirely to
`outputs/java_bank/target/cpp/reports/19_migration_complexity.json`:

- Migration Complexity's `SPEC` declares `loc` as an **optional** input, not
  a required one (contrast with Maintainability Complexity above, which
  declares the same field required and consequently gates outright).
- Projection Rule 3 strips `loc` from every unit, unconditionally, for
  every target — this run's tree carries no `loc` field at all
  (`metrics.total_loc: 0` in the report, and every item's own `"loc": 0`).
- Because the field is only optional, `_core.run()`'s central gate does
  **not** block Migration Complexity — it still runs, but its own
  already-existing internal code (not anything this target-fit skill run wrote or
  patched) substitutes zero wherever it would have read `loc`, per the
  `fields_stripped_caveat` this run's own `projection` block states in full.
- The report's own metrics confirm this mechanically: every item's
  `volume_score` is correspondingly small or zero — e.g. `Bank.transfer`'s
  `volume_score` is **0.8** here (driving its item score to 3.8, tied with
  `TransactionLog.totalFor` at the same 3.8 for this run's ceiling), where
  on the source side the same unit's real 16 lines of code fed a materially
  larger volume component (driving the source-side ceiling item to 4.1).
  `metrics.total_volume_score` for this run is **4.7**, against a
  `total_blocker_score` of **42.0** — the blocker component dominates the
  portfolio total precisely because the volume component collapsed toward
  zero.
- `blocker_score` values, by contrast, are **unaffected** — they come from
  `unstructured_jumps`, `dynamic_sql`, and similar fields untouched by
  volume stripping (every item's `unstructured_jumps: 0`,
  `dynamic_sql: 0`), which is why every unit's blocker profile and the
  100%-rehost strategy distribution (`strategy_distribution: {"rehost": 36}`,
  `blocker_breakdown: {}`) are identical between source and target, and
  identical to the earlier Python run as well.
- The report's own `confidence.reasons` names `loc` explicitly as one of
  five absent optional inputs (`sql`, `platform_calls`,
  `dynamic_constructs`, `conditional_compilation`, `loc`), and confidence
  fell from 0.6 (source) to **0.5** (target) specifically because of this —
  the analyzer is telling you, in its own words, that it is less sure of
  this number than it was on the source side, for exactly this reason.
- Note that this analyzer's `target_language` field in its own report is
  `null` and its `derived_from`/`interpretation` content makes no reference
  to any specific target language at all — its scoring logic reacts only to
  which fields the tree carries, never to which target descriptor caused
  those fields to be stripped. That is precisely why this run's Migration
  Complexity numbers (3.8, confidence 0.5) are numerically identical to the
  Python-target run's numbers against this same tree: the mechanism
  producing the delta is target-agnostic by construction.

**Conclusion for this metric: the 4.1 → 3.8 delta is an artifact of an
optional field defaulting toward zero inside Migration Complexity's own
pre-existing, already-audited code — not a finding that C++ is cheaper to
migrate to than staying in Java.** Any migration-planning use of this
number should use the source-side 4.1 (computed from real LOC) as the
authoritative volume-weighted figure, and treat the target-side 3.8 as a
confidence-discounted approximation missing exactly the signal this section
describes.

---

## Conclusion and recommended next steps

This run's real, independently-computed target-side scores land at the same
**L3 (moderate)** worst case as the source-side Java run, with a mean level
of **1.88** (vs. source's 1.94) — a difference fully explained by one fewer
skill measuring at all (17/20 vs. 18/20), not by any dimension actually
looking better in C++. Of the 20 metrics, **17 ran to a real, fresh
target-side conclusion this run**; every one of the 17 landed at the same
level as its source-side counterpart, and 15 of those 17 landed at the
*exact same score* as well — because projection dropped zero units for this
codebase (it contains no GOTO/ALTER/PERFORM_THRU/FALL_THROUGH constructs,
so C++'s genuine `goto` support was never exercised either way) and kept
`types` intact (C++ has a real object model with native multiple
inheritance). The two skills whose reported figures did shift (Structural
Complexity's confidence, not score; Migration Complexity's score,
genuinely) both trace to the same cause: the unconditional stripping of
`loc`/`comment_lines`/`halstead`, interacting differently with each skill's
own `requires` vs. `optional` declaration for that field.

Concrete takeaways specific to a Java→C++ decision for this codebase:

1. **This descriptor is unreviewed and freshly drafted.** Before this
   report's findings are used for any real planning decision, have a
   maintainer check `.claude/target_fit/languages/cpp.json` field-by-field
   against real C++ documentation and promote it out of provisional status.
   Every score above should be treated as directionally sound but not final
   until that happens.
2. **Maintainability Complexity cannot be answered for the C++ target at
   all**, for any target, ever — this is structural to the harness's refusal
   to invent a verbosity ratio, not a gap specific to this run. If a
   maintainability-index-style figure is needed for a C++ target, it can
   only come from measuring real, already-translated C++ code with its own
   `loc`, not by projecting the Java figure.
3. **Do not use Migration Complexity's target-side 3.8 as evidence C++ is
   cheaper to migrate to.** Use the source-side 4.1 (real LOC-weighted) as
   the authoritative volume figure, and treat this run's number only as
   confirmation that no *new* translation blocker appears for a C++ target —
   which is a real and useful finding, just not the one the raw score-delta
   suggests. This same caveat applied identically to the earlier Python-
   target run, for the identical mechanism.
4. **C++'s genuine `goto` support is a real fact about the language, but not
   a finding about this codebase.** `java_bank` contains zero unstructured
   jump constructs of any kind, so this descriptor field never changed
   which units survived projection. It would matter for a codebase that
   actually used `GOTO`/`ALTER`-style constructs — this one simply isn't
   that codebase.
5. **Nothing about this codebase's actual shape resists a C++ target.** Zero
   units were dropped in projection, `types` survived intact, and the 17
   skills that did run found the same coupling, cohesion, testability and
   runtime-growth concerns Agent 3 already flagged for the Java source
   (`CompoundInterestPolicy.rate`'s recursion, `Account`'s and
   `TransactionLog$Entry`'s constructors' hidden-state friction, `Bank`'s
   and `util.Validation`'s low cohesion) — those are properties of the
   *code*, not of the *language*, and migrating to C++ will not resolve any
   of them on its own. C++'s lack of garbage collection and its manual
   memory management model are real considerations for a Java→C++ migration
   that this harness's 20 metrics do not measure at all — they are outside
   the scope of any of the 20 complexities defined here, and should be
   tracked separately by whoever plans this migration.
