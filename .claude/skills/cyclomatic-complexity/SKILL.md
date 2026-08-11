---
name: cyclomatic-complexity
description: >
  The number of linearly independent paths through a unit. It is the lower
  bound on how many test cases you need for full branch coverage, and the
  most widely understood complexity number in existence. Every estimate
  conversation starts here.
  Implemented deterministically by `.claude/complexities/01_cyclomatic_complexity.py`; used by the Complexity Agent (1_complexity) in tier band 2 (structural).
---

# 01 - Cyclomatic Complexity

> **What it is** — The number of linearly independent paths through a unit.
> **When to use it** — It is the lower bound on how many test cases you need for full branch coverage, and the most widely understood complexity number in existence.
> **How it works** — v(G) = 1 + decision nodes.

## Purpose

**What it measures.** The number of linearly independent paths through a unit.

**Why it matters.** It is the lower bound on how many test cases you need for full branch coverage, and the most widely understood complexity number in existence. Every estimate conversation starts here.

## Method

v(G) = 1 + decision nodes. ELSE and DEFAULT deliberately add nothing: the path already exists as the false arm of the branch above them. Counting them inflates every unit by one per branch, which is the most common way this metric is got wrong.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `units` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `cfg` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `loc` | Optional | Absent -> confidence reduced, reason recorded |

- **Scope:** unit
- **Tier band:** 2 (structural)
- **Depends on:** none
- **Direction:** `higher_is_worse`

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "cyclomatic_complexity",
  "sno": 1,
  "complexity": "Cyclomatic Complexity",
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
python .claude/complexities/01_cyclomatic_complexity.py TREE.json
python .claude/complexities/01_cyclomatic_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/01_cyclomatic_complexity.py
python .claude/complexities/01_cyclomatic_complexity.py --spec
```
