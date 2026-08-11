---
name: nesting-complexity
description: >
  How deeply control structures are stacked inside one another. Nesting
  depth is the cheapest reliable predictor of reading difficulty, and it
  maps directly to a fix: flatten it. Depth is also what cyclomatic
  complexity is blindest to - twenty flat branches and four branches nested
  four deep can score the same v(G), and only one of them is genuinely hard
  to follow.
  Implemented deterministically by `.claude/complexities/05_nesting_complexity.py`; used by the Complexity Agent (3_complexity) in tier band 2 (structural).
---

# 05 - Nesting Complexity

> **What it is** — How deeply control structures are stacked inside one another.
> **When to use it** — Nesting depth is the cheapest reliable predictor of reading difficulty, and it maps directly to a fix: flatten it.
> **How it works** — Maximum and mean nesting depth per unit, plus the amount of code sitting at excessive depth.

## Purpose

**What it measures.** How deeply control structures are stacked inside one another.

**Why it matters.** Nesting depth is the cheapest reliable predictor of reading difficulty, and it maps directly to a fix: flatten it. Depth is also what cyclomatic complexity is blindest to - twenty flat branches and four branches nested four deep can score the same v(G), and only one of them is genuinely hard to follow.

## Method

Maximum and mean nesting depth per unit, plus the amount of code sitting at excessive depth. Reports the deepest construct so the finding points somewhere specific.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `units` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `cfg` | **Required** | Absent -> `insufficient_input`, analyzer never runs |

- **Scope:** unit
- **Tier band:** 2 (structural)
- **Depends on:** none
- **Direction:** `higher_is_worse`

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "nesting_complexity",
  "sno": 5,
  "complexity": "Nesting Complexity",
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
python .claude/complexities/05_nesting_complexity.py TREE.json
python .claude/complexities/05_nesting_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/05_nesting_complexity.py
python .claude/complexities/05_nesting_complexity.py --spec
```
