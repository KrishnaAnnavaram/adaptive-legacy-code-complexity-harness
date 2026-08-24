---
name: target-fit-complexity
description: >
  Project a Normalized Tree onto a NAMED target language and score it with the
  real 20 complexity analyzers, producing a target-side complexity artifact
  structurally identical to the source-side one. Invoke this ONLY when the
  request names a target language for the complexity run — e.g. "check
  complexity for target Python", "how complex is this if we move it to Java",
  "target language: cobol". If no target language is named, do NOT invoke this
  skill; the Complexity Agent runs its normal source-side pass alone. This
  skill is the on-demand target-language counterpart to the Complexity Agent
  (3_complexity): it never carries a source number forward — it builds a
  projected tree and runs the same 20 analyzers a second time against it, then
  reads the source-side artifact only to build a comparison section. Works for
  any source/target pair purely from which descriptor file is named; nothing
  about a specific language pair is hardcoded. A target is only scored once its
  descriptor has been reviewed and promoted out of
  .claude/target_fit/languages/_pending/.
---

# Target-Fit Complexity — skill for the Complexity Agent

## When this skill fires

The Complexity Agent invokes this skill **only when a target language is named**
in the request. A target language is any statement of "where is this codebase
going" — phrasings like *"check complexity for target Python"*, *"score this as
if migrated to Java"*, *"target: cobol"*, *"how complex would the Python version
be"*.

If the request names **no** target language, this skill does not run at all. The
Complexity Agent does its normal source-side 20-analyzer pass and stops there.
Never assume a target — if it is ambiguous whether a target was named, ask
before running this skill; do not guess one.

## What it answers

One question, defensibly, for real, not by carrying a number forward: *if this
codebase's destination is language X, what does each of the 20 complexity
measurements actually come out to, computed against a tree that honestly
represents what survives translation?*

Three commitments govern everything below — the same discipline the source-side
run holds:

**Never invent a target's shape.** A target with no promoted descriptor gets
`insufficient_input` naming the target and listing what is available. It never
gets a guessed capability profile.

**Never invent a projected tree.** A unit containing a construct the target
cannot express (a `GOTO`/`ALTER`-style jump the descriptor declares unsupported)
is dropped from the projected tree, logged with its reason. It is never given an
invented restructured shape, and never left in with a stripped CFG that would
look falsely simple.

**Never invent a number for code that doesn't exist.** `loc`, `comment_lines`
and `halstead` are stripped from every projected unit, for every target, always
— there is no honest verbosity ratio to apply. This gates Structural and
Maintainability Complexity through their own declared `requires`, the same
central mechanism every analyzer already uses — not a rule enforced by hand.

---

## Inputs

| Parameter | Description | Required |
|---|---|---|
| `TREE` | Path to the Normalized Tree JSON (the parser's output), e.g. `outputs/java_bank/normalized_tree.json` | Yes |
| `TARGET_LANGUAGE` | The target to project onto, e.g. `python`, `java`, `cobol`, `plsql` | Yes |
| `SOURCE_ARTIFACT` | Path to the source-side `complexity_artifact.json`, for the comparison section only | No (default: look for `complexity_artifact.json` next to `TREE`) |
| `OUT_DIR` | Override for where target results are written | No (default: `<dir of TREE>/target/<TARGET_LANGUAGE>/`) |

Both required parameters come from the request — e.g. "check complexity of
`outputs/java_bank/normalized_tree.json` for target Python." `TARGET_LANGUAGE`
being present is the whole reason this skill was invoked; if it somehow is not
stated, stop and ask — never assume one.

---

## Source-side pass: run it only if it isn't already done

This skill needs a source-side `complexity_artifact.json` for its comparison
section, and the Complexity Agent's normal run produces exactly that. So, before
projecting:

```
1. Look for the source-side complexity_artifact.json — first at SOURCE_ARTIFACT
   if given, otherwise next to TREE (same directory), i.e. the Complexity
   Agent's normal OUTPUT_DIR for this tree.

2. IF it already exists:
     Skip the source-side pass entirely. It is already done; re-running it would
     just reproduce the same deterministic bytes. Go straight to projection and
     pass this artifact in as the comparison baseline.

3. IF it does NOT exist:
     Run the Complexity Agent's normal source-side pass first
     (python .claude/complexities/run_pipeline.py TREE.json -o <OUTPUT_DIR>),
     which writes complexity_artifact.json. THEN project and score the target.
     Both artifacts end up on disk — source-side in OUTPUT_DIR, target-side in
     OUT_DIR.
```

The rule in one line: **the source pass runs at most once — reuse it if present,
produce it if not, and always run the target pass.**

---

## Descriptor lifecycle

Every target language is one JSON file under `.claude/target_fit/languages/`,
schema in `.claude/target_fit/schema.md`, promoted out of `languages/_pending/`
only after a human review:

```
1. DRAFT    - a new <lang>.json is written to languages/_pending/,
              marked "source": "drafted", "reviewed": false.
2. REVIEW   - a person checks every field against real documentation for
              that language, not general impression, and corrects it.
3. PROMOTE  - the file moves into languages/ and "reviewed" flips to true.
4. USE      - target_fit.py only ever reads from languages/, never from
              languages/_pending/.
```

The four shipped descriptors (`cobol`, `plsql`, `java`, `python`) currently carry
`"reviewed": false` and must be treated with the same caution as any future
addition. What these descriptors govern is not per-metric reinterpretation but
the two facts that drive tree *projection* itself:
`supports_goto` / `supports_alter_style_dynamic_jump` (which units survive) and
`multiple_inheritance` (whether `types` survives).

---

## Execution order

```
1. VALIDATE
   Confirm TREE exists and parses as JSON. Missing -> insufficient_input.

2. RESOLVE TARGET
   Look for .claude/target_fit/languages/<TARGET_LANGUAGE>.json.
   Missing -> insufficient_input, list available targets, offer to draft into
   languages/_pending/ (never promote or score against it in the same turn).

3. SOURCE BASELINE
   Apply the "run it only if it isn't already done" rule above.

4. PROJECT
   .claude/target_fit/project_tree.py's project_tree(tree, descriptor):
     - drops any unit whose CFG contains a jump construct (GOTO/ALTER/
       PERFORM_THRU/FALL_THROUGH) the descriptor says it cannot express,
       logging unit id + reason
     - drops `types` entirely if the target has no object model
       (multiple_inheritance is null)
     - strips loc/comment_lines/halstead from every surviving unit,
       unconditionally
     - carries everything else through unchanged

5. RUN THE REAL 20 ANALYZERS
   .claude/complexities/run_pipeline.py's own discover(), order(), execute() and
   consolidate() — the exact functions the source-side pipeline uses — run
   against the PROJECTED tree. Every analyzer gates on its own declared
   requires/optional exactly as it always does. This is not a duplicate
   implementation; it is the same 20 scripts on a different tree.

6. COMPARE (traceability only)
   Read the source-side complexity_artifact.json resolved in step 3. Pair its
   per-sno score/level against this run's per-sno score/level into a
   `comparison` section. This step never feeds step 5's numbers — it runs
   strictly after, on the already-finished target-side results.

7. HUMAN REPORT
   Write OUT_DIR/complexity_report.md yourself, with the Write tool — not
   generated by the script. Same depth and sourcing discipline as the
   Complexity Agent's own complexity_report.md: a per-metric deep dive for
   every one of the 20 rows, stating the target's real status/score/level, how
   many units were dropped and why (if any), whether the metric gated to
   insufficient_input and on which required field, and the source-side
   comparison number for context — never presenting the comparison number as if
   it were the mechanism, always as "here is what changed and why." State the
   descriptor's reviewed/unreviewed status up front, before any finding.
```

Steps 4–6 are implemented by `.claude/target_fit/target_fit.py`:

```bash
python .claude/target_fit/target_fit.py TREE.json --target TARGET_LANGUAGE [-o OUT_DIR] [--source-artifact PATH]
```

Step 7 (the human report) is not part of that script — write it with the Write
tool after the run completes.

---

## Output

```
<dir of TREE>/
  target/
    <target_language>/
      reports/
        01_cyclomatic_complexity.json   ← one full report per analyzer that ran, same shape the source side writes
        ...
      complexity_artifact.json          ← consolidate()'s own shape, plus target_language/source_language/
                                           descriptor_reviewed/projection/source_baseline/comparison
      complexity_report.md              ← human companion, written by you in step 7
```

Running the same tree against a second target writes a sibling directory
(`target/java/` next to `target/python/`) — nothing is overwritten.

---

## Constraints

- **Read-only on the tree and on the source-side output.** Never modify either.
  `project_tree.py` deep-copies before touching anything.
- **No hardcoded language logic, in either direction.** Every fact used to decide
  what survives projection comes from the descriptor's existing fields
  (`supports_goto`, `supports_alter_style_dynamic_jump`, `multiple_inheritance`).
  Nothing here should ever read "if target == 'python'".
- **No duplicate analyzer logic.** Every one of the 20 target scores comes from
  literally calling `run_pipeline.py`'s own functions and the analyzer modules —
  never a second implementation of cyclomatic counting, LCOM4, or anything else.
- **No invented conversion ratios.** `loc`/`comment_lines`/`halstead` are
  dropped, never estimated by any multiplier.
- **A score difference from the source baseline is not automatically a finding.**
  Some analyzers (e.g. Migration Complexity) declare a stripped field merely
  *optional*; their own existing code then substitutes zero for it internally
  rather than gating, which can shift a score without meaning "the target
  genuinely needs less work." Check `confidence.reasons` on that specific report
  before treating a comparison delta as real — see `docs/target-fit-contract.md`.

---

## Verification

Before treating a run's output as trustworthy:

- Confirm `descriptor_reviewed` — if `false`, the confidence score and reasons
  already say why; do not round that up in the human report.
- Confirm `projection.units_dropped` names real units with real reasons, and that
  `coverage` reflects the actual gated/ok count from step 5, not a hand-adjusted
  number.
- Confirm the `comparison` section's `target_score`/`target_level` came from step
  5's real run, never copied from the source side.
- Running the same tree/target twice produces byte-identical output aside from
  the one `generated_at` stamp `consolidate()` writes once.

---

## Contract

Full rules for this projection path live in
[`docs/target-fit-contract.md`](../../../docs/target-fit-contract.md) — the
companion to `docs/analyzer-contract.md`, scoped to the target-fit path.
