# How to build a complexity analyzer that works in any harness

This is the answer to "what is the best way to build these so they are reusable
anywhere". Everything here is enforced by [`_core.py`](_core.py) and audited by
[`tools/judge.py`](../tools/judge.py) — the rules are not advice, they are checked.

---

## The shape

```python
"""
Complexity #NN - Name
=====================
What is it?      one line
Why needed?      why a modernization programme cares
How it works?    the actual method
Input required   which Normalized Tree fields
"""
from _core import Spec, Tree, cli_main, result, level_from, worst

SPEC = Spec(
    id="my_complexity", sno=21, name="My Complexity", tier="structural",
    requires=["units", "cfg"],          # hard: absent -> insufficient_input
    requires_any=["sql", "cursors"],    # at least one must be present
    optional=["loc"],                   # absent -> confidence drops automatically
    depends_on=[1, 7],                  # composites only
    summary="one line for the harness listing",
)

def analyze(tree_raw):
    tree = Tree(tree_raw)
    degraded = tree.require(SPEC)
    ...
    return result(SPEC, tree, level=..., score=..., headline=..., metrics=...,
                  items=..., hotspots=..., confidence=...)

if __name__ == "__main__":
    raise SystemExit(cli_main(analyze, SPEC))
```

That is the whole thing. It works imported, from a shell, and in a pipe.

---

## The seven rules

**1. Pure function first.** `analyze(tree) -> dict`. No file IO, no globals, no
printing, no network. The CLI is a thin shell around it, never the reverse. An
analyzer that only works from the command line cannot be embedded in anyone's
harness.

**2. One tree format.** Everything reads the same Normalized Tree, documented at
the top of `_core.py`. Two formats in one repo means N×M glue and silent
mismatches — this repository has already paid that bill once.

**3. Self-describing.** `SPEC` tells a harness what the analyzer needs, what tier
it sits in, and what it depends on. A harness can discover, filter and order
analyzers with no hardcoded list. That is what makes "drop in a file" work.

**4. Declare your inputs and fail loud.** If the tree lacks what you need, return
`insufficient_input` naming the gap. **Never return a zero.**

> This rule is the reason the contract exists. Earlier versions of this repo
> returned clean-looking zeros — and in one batch, fully-formed reports built
> from hardcoded demo data — when handed input they could not read. Nothing
> distinguished that from a genuine clean result. A wrong number that looks
> right is worse than no number, because nobody can tell it is wrong.

**5. Uniform output envelope.** Same shape from every analyzer, so a harness
merges results without a special case per analyzer.

**6. Deterministic.** Same tree in, same bytes out. No timestamps inside an
analyzer's output — the pipeline stamps the run once. No set-iteration order
leaking into results.

**7. Standard library only.** Legacy modernization frequently happens air-gapped,
where installing a package is a change request.

---

## What the harness does for you

Do **not** reimplement these — `_core` handles them centrally so every analyzer
behaves identically:

| Concern | Handled where |
|---|---|
| Enforcing `requires` before `analyze` runs | `_core.run()` |
| Dropping confidence when an `optional` input is missing | `_core.normalize()` |
| Mapping exceptions onto the envelope | `_core.run()` |
| CLI, stdin, `-o`, `--spec` | `_core.cli_main()` |
| Tier ordering and dependency depth | `run_pipeline.py` |
| Feeding upstream reports to composites | `run_pipeline.py` |

Shared helpers worth using rather than rewriting, so that all analyzers agree on
the same numbers: `Tree.cyclomatic()`, `Tree.max_depth()`, `Tree.walk_depth()`,
`Tree.count()`, `level_from()`, `worst()`.

---

## Two things that are easy to get wrong

**ELSE is not a decision point.** `DECISION_NODES` excludes `ELSE` and `DEFAULT`
deliberately. The path already exists as the false arm of the branch above. Count
them and you inflate every unit by one per branch across the whole codebase.

**Unmeasurable is not zero.** If a value cannot be computed from what you were
given, say so. Analyzer #18 originally defaulted an unknown line count to 1,
which made every config read look maximally scattered and manufactured a finding
out of missing data. The judge caught it; the fix was to score 0 and lower
confidence, not to guess.

---

## Verify before you commit

```bash
python run_pipeline.py samples/cobol_payroll.tree.json -o out
python tools/judge.py samples/cobol_payroll.tree.json --self-test
```

The judge runs ten adversarial checks per analyzer:

| | Check |
|---|---|
| C1 | Full envelope, correct id |
| C2 | Starved of declared inputs → `insufficient_input`, not a zero |
| C3 | Empty tree → same |
| C4 | Same tree twice → byte-identical |
| C5 | No input at all → fails visibly, no fabricated demo report |
| C6 | L4/L5 backed by items or hotspots — a severe score with no evidence is an assertion |
| C7 | Confidence declared, and anything below 1.0 explained |
| C8 | Score finite, non-negative, not saturating its band |
| C9 | Runs under any language label |
| C10 | **Honest SPEC** — strip undeclared inputs; if the score moves while confidence stays 1.0, the SPEC is incomplete and the analyzer degrades silently |

C10 is the one that matters most. C2 can only ever exercise the central gate, so
it proves the SPEC is *wired*, not that it is *complete*. C10 is what proves the
analyzer isn't quietly reading things it never declared — it caught two real
defects in analyzers #18 and #19 on its first run.

`--self-test` additionally audits `tools/99_canary_complexity.py`, an analyzer
that is defective on purpose. It **must** come back CRITICAL. A suite that only
ever reports PASS tells you nothing about the code, only about the suite.
