# Architecture decisions

Each entry records what was decided, what it rules out, and what would change it.

---

## AD-01 — One tree format, not two

**Decision.** Every skill reads the same Normalized Tree.

**Context.** The 20 analyzers were originally written against two mutually
incompatible shapes: a recursive `{kind, children[]}` tree, and
`{language, units[], call_graph, dependency_graph}`. They shared no field names.

**Why it mattered more than it looked.** The mismatch did not raise. Feeding a
Style-A tree to a Style-B analyzer produced `units seen: 0` and a clean-looking
result. Analyzers 8–14 went further and ignored their file argument entirely,
printing complete reports from hardcoded demo data — verified by handing one a
file declaring `language: ZZZ-MY-FILE` with 1 unit and getting back
`language: java` with 2 units.

**Rejected alternative.** Keep both and bridge between them. A bridge is N×M glue
and it cannot invent the fields the other shape has no vocabulary for.
`tools/tree_bridge.py` still exists for legacy trees, and it names the analyzers
that will under-report rather than silently producing zeros.

**Reversal trigger.** A parser that genuinely cannot emit the unified shape.

---

## AD-02 — Declared inputs, gated centrally

**Decision.** Each skill declares `requires` / `requires_any` / `optional` in its
`SPEC`. `_core.run()` enforces them **before** the skill is invoked. Unmet
requirements produce `insufficient_input` naming the field.

**Why central.** Enforcement left to each author is enforcement that will be
forgotten. Putting the gate in one place means a skill physically cannot run
starved, whatever its author did or did not remember.

**The rule.** *A clean zero from a starved skill is indistinguishable from a
genuine clean result.* Absence of measurement and absence of complexity are
different facts and must never collapse into the same output.

**Consequence.** Coverage is reported as `N/20 measured` with reasons for the
rest. An incomplete run says so in its headline.

---

## AD-03 — Pure function first, CLI second

**Decision.** Every skill is `analyze(tree) -> dict` with no file IO, no globals,
no printing. The CLI is a thin shell around it.

**Why.** Portability into *any* harness is the requirement. A script that only
works from a command line cannot be embedded. A function that returns a dict can
be called a thousand times in-process, tested directly, and wrapped however the
host needs.

**Rejected alternative.** CLI-first with a JSON artifact on disk. It works
standalone and is unusable as a library.

---

## AD-04 — Self-describing skills, no registry

**Decision.** Skills are discovered by scanning `.claude/scripts/[0-9][0-9]_*.py`
and reading each module's `SPEC`. There is no list to maintain.

**Why.** A hardcoded list is a second place to update, and the failure mode is
silent: the skill exists, works, and never runs. Discovery makes "drop in a file"
literally true.

**Cost.** Import-time errors in one script must not break discovery — the
pipeline reports and skips them.

---

## AD-05 — Tier bands with a deterministic tie-break

**Decision.** `size → structural → data → coupling → hazard → composite`, then
dependency depth, then `sno`.

**Why bands.** Composites consume primitives. Maintainability needs size and
branching; Migration needs Database, Testability, Runtime and Architectural.
Running them first yields a number computed from nothing.

**Why the numeric tie-break.** Reproducibility. Without a final deterministic
key, dictionary iteration order leaks into the artifact and two runs over the
same tree differ.

---

## AD-06 — Levels L1–L5, not raw scores

**Decision.** Every skill reports a band as well as a score, and bands are
language-calibrated where it matters.

**Why.** Raw scores are not comparable across skills or languages. `v(G) = 24` is
a refactoring ticket in Java and unremarkable in a COBOL paragraph — a threshold
of 10 flags every production paragraph and therefore discriminates nothing.
Cyclomatic bands are 10/20/35/50 by default and 15/35/55/75 for COBOL.

**Known limit.** Calibration is judgement informed by published practice, not a
statistical study of a reference corpus. Re-fit against a real codebase once
enough runs exist.

---

## AD-07 — Corroboration before a unit is called a hotspot

**Decision.** A unit is a hotspot only when **two or more independent skills**
band it L4/L5.

**Why.** A unit flagged by one skill is usually that skill's bias — a long
paragraph of straight-line assignments trips size and nothing else. Agreement
across independent skills is the cheapest available signal that a finding is real,
and it needs no tuned threshold.

---

## AD-08 — The judge must be able to fail

**Decision.** `tools/judge.py` runs ten adversarial checks per skill, and
`tools/99_canary_complexity.py` is defective on purpose and must come back
CRITICAL under `--self-test`.

**Why.** The judge passed all 20 skills on its first run. That is not evidence the
skills are sound; it is equally consistent with a judge that cannot detect
anything. The canary was planted to find out — it caught 4 of 5 defects and
**missed one**, which exposed that check `C2` only ever exercises the central gate
and therefore proves a SPEC is *wired*, not *complete*.

`C10` was added in response: strip undeclared inputs, and fail the skill if its
score moves while confidence stays at 1.0. It immediately caught two real defects
in skills #18 and #19 — both read line counts they never declared, and #18
treated an unknown line count as maximal scatter, manufacturing a finding out of
missing data.

**Principle.** A test suite that only ever reports PASS tells you nothing about
the code, only about the suite.

---

## AD-09 — Standard library only

**Decision.** No third-party dependencies in any skill.

**Why.** Legacy modernization frequently happens inside air-gapped client
environments where installing a package is a change request measured in weeks. A
harness that cannot run there cannot be used where it is most needed.

---

## AD-10 — Deterministic output

**Decision.** No timestamps inside a skill's report. The pipeline stamps the run
once, in the artifact.

**Why.** Reports must be diffable across runs to see whether complexity moved.
A timestamp in every report makes every diff non-empty and useless.

---

## AD-11 — plsql_to_brd is never committed

**Decision.** `plsql_to_brd/` is in `.gitignore` with an explicit warning comment.

**Why.** It is a separate repository that happens to sit inside this working
directory. It carries its own `.git`, so `git add .` would either commit it as a
broken submodule reference or absorb its history. Neither is cleanly recoverable
once pushed.
