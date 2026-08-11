---
name: npath-complexity
description: >
  The number of distinct acyclic execution paths through a unit. Cyclomatic
  complexity counts the paths you must test to cover every EDGE. NPath
  counts the paths that actually EXIST. The two diverge violently: ten
  sequential if statements give v(G) = 11 and NPath = 1,024. That gap is why
  "we have full branch coverage" and "we tested the combinations" are
  different claims, and why some units cannot be exhaustively tested at all.
  Implemented deterministically by `.claude/complexities/06_npath_complexity.py`; used by the Complexity Agent (3_complexity) in tier band 2 (structural).
---

# 06 - NPath Complexity

> **What it is** — The number of distinct acyclic execution paths through a unit.
> **When to use it** — Use it when full branch coverage is being claimed as sufficient - NPath shows how many untested combinations remain behind it.
> **How it works** — Paths multiply through sequence and through nested branches; counting is capped once a unit is beyond exhaustive testing anyway.

## Purpose

**What it measures.** The number of distinct acyclic execution paths through a unit.

**Why it matters.** Cyclomatic complexity counts the paths you must test to cover every EDGE. NPath counts the paths that actually EXIST. The two diverge violently: ten sequential if statements give v(G) = 11 and NPath = 1,024. That gap is why "we have full branch coverage" and "we tested the combinations" are different claims, and why some units cannot be exhaustively tested at all.

## Method

Paths multiply through sequence and add through branches. A unit with independent branches b1..bn has PROD(paths(bi)).

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `units` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `cfg` | **Required** | Absent -> `insufficient_input`, analyzer never runs |

- **Scope:** unit
- **Tier band:** 2 (structural)
- **Depends on:** none
- **Direction:** `higher_is_worse`

## Overflow

NPath grows multiplicatively and reaches astronomic values on real legacy
code. Counting is capped at CAP; beyond it the unit is reported as
`capped: true` with `>= CAP`. An exact figure of 10^47 conveys nothing that
"beyond exhaustive testing" does not, and computing it invites overflow
handling bugs for no analytical gain.

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "npath_complexity",
  "sno": 6,
  "complexity": "NPath Complexity",
  "tier": "structural",
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
| Tree contains no units | - | Return `insufficient_input` |
| Unhandled exception | `error` | Caught by `_core.run()`, returned as `status: error` with the exception text. The pipeline continues. |

## Invocation

```bash
python .claude/complexities/06_npath_complexity.py TREE.json
python .claude/complexities/06_npath_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/06_npath_complexity.py
python .claude/complexities/06_npath_complexity.py --spec
```
