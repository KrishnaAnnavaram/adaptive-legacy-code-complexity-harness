---
name: testability-complexity
description: >
  How hard it is to get a unit under test at all - and how many tests it
  would then take to cover it. Modernization is only safe behind a
  characterization-test net. Testability decides whether that net can be
  built, and it is the metric that most reliably predicts the true cost of a
  legacy rewrite. Two units with identical cyclomatic complexity can differ
  by an order of magnitude in test effort.
  Implemented deterministically by `.claude/complexities/16_testability_complexity.py`; used by the Complexity Agent (3_complexity) in tier band 6 (composite).
---

# 16 - Testability Complexity

> **What it is** — How hard it is to get a unit under test at all - and how many tests it would then take to cover it.
> **When to use it** — Modernization is only safe behind a characterization-test net.
> **How it works** — Separates test burden (how many paths need covering) from test friction (hidden inputs, side effects, missing seams, non-determinism).

## Purpose

**What it measures.** How hard it is to get a unit under test at all - and how many tests it would then take to cover it.

**Why it matters.** Modernization is only safe behind a characterization-test net. Testability decides whether that net can be built, and it is the metric that most reliably predicts the true cost of a legacy rewrite. Two units with identical cyclomatic complexity can differ by an order of magnitude in test effort.

## Method

Separates the two things people conflate: (a) TEST BURDEN  - how many paths need covering (cyclomatic). (b) TEST FRICTION - what stands between you and invoking the unit in isolation: hidden inputs, side effects, hard dependencies that need mocking, non-determinism, and missing seams. Burden is linear and predictable. Friction is what actually blocks a test being written, so it is weighted far harder.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `units` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `cfg` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `references` | Optional | Absent -> confidence reduced, reason recorded |
| `globals` | Optional | Absent -> confidence reduced, reason recorded |
| `writes` | Optional | Absent -> confidence reduced, reason recorded |
| `call_graph` | Optional | Absent -> confidence reduced, reason recorded |
| `dependency_graph` | Optional | Absent -> confidence reduced, reason recorded |
| `meta` | Optional | Absent -> confidence reduced, reason recorded |

- **Scope:** unit
- **Tier band:** 6 (composite)
- **Depends on:** #1, #4
- **Direction:** `higher_is_worse`

### Tree fields consumed

```
tree = {
  "language": "java",
  "units": [ {
      "id","name","owner_type","loc",
      "params":     [name, ...],
      "references": [data_id, ...],                # data the unit touches
      "globals":    [data_id, ...],                # optional: shared/global state
      "writes":     [data_id, ...],                # optional: mutated state
      "cfg": {"node_type","children":[...]},
      "meta": {                                    # all optional
          "static":       bool,                    # no seam for substitution
          "constructor_params": int,
          "nondeterministic": bool                 # clock / random / env / uuid
      }
  }, ... ],
  "call_graph":       {"edges":[{"from","to"}, ...]},
  "dependency_graph": {"edges":[{"from","to","kind":"db|external|platform|library|config|api"}, ...]}
}

CFG node types consumed:
    decision nodes (IF/FOR/WHILE/CASE/CATCH/AND/OR/...)  -> test burden
    IO, FILE, NETWORK, DB, SQL, PLATFORM                 -> friction (must be faked)
```

## Language Neutrality

Nothing here is language-specific. A COBOL paragraph reading WORKING-STORAGE,
a PL/SQL package member reading a package global, and a Java method reading a
static field are all "hidden input" and score identically.

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "testability_complexity",
  "sno": 16,
  "complexity": "Testability Complexity",
  "tier": "composite",
  "status": "ok | insufficient_input | error",
  "summary": { "level": "L1..L5", "score": 0.0, "headline": "..." },
  "metrics": { },
  "hotspots": [ ],
  "items": [ ],
  "confidence": { "score": 1.0, "reasons": [] },
  "inputs_used": [ ],
  "inputs_missing_optional": [ ]
}
```

## Levels

| Level | Meaning |
|---|---|
| `L1` | trivial |
| `L2` | low |
| `L3` | moderate |
| `L4` | high |
| `L5` | severe |

## Error handling

| Condition | Severity | Action |
|---|---|---|
| A required input is absent | - | Return `insufficient_input` naming the field. **Never return a zero** - a clean zero from a starved analyzer is indistinguishable from a genuine clean result. |
| An optional input is absent | `warning` | Run in degraded mode; confidence reduced and the reason recorded in `confidence.reasons` |
| An upstream report is missing | `warning` | Derive what is possible from the tree; list the gap in `derivation.estimated` |
| Tree contains no units | - | Return `insufficient_input` |
| Unhandled exception | `error` | Caught by `_core.run()`, returned as `status: error` with the exception text. The pipeline continues. |

## Invocation

```bash
python .claude/complexities/16_testability_complexity.py TREE.json
python .claude/complexities/16_testability_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/16_testability_complexity.py
python .claude/complexities/16_testability_complexity.py --spec
```
