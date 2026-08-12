---
name: structural-complexity
description: >
  The shape and size of the codebase: how much there is, how it is
  distributed, and whether that distribution is healthy. Every other metric
  reports a per-unit score. This one reports the SHAPE of the estate, which
  is what drives planning. Ten thousand lines spread evenly over 200 units
  is a very different job from the same ten thousand lines with 80% in three
  units - and the average complexity is identical in both cases.
  Implemented deterministically by `.claude/complexities/07_structural_complexity.py`; used by the Complexity Agent (3_complexity) in tier band 1 (size).
---

# 07 - Structural Complexity

> **What it is** — The shape and size of the codebase: how much there is, how it is distributed, and whether that distribution is healthy.
> **When to use it** — Use it first on any new estate, to see whether size is spread evenly or concentrated in a few huge units.
> **How it works** — Size and statement counts per unit, then distribution across the whole tree: concentration in the largest units, spread, and outliers.

## Purpose

**What it measures.** The shape and size of the codebase: how much there is, how it is distributed, and whether that distribution is healthy.

**Why it matters.** Every other metric reports a per-unit score. This one reports the SHAPE of the estate, which is what drives planning. Ten thousand lines spread evenly over 200 units is a very different job from the same ten thousand lines with 80% in three units - and the average complexity is identical in both cases.

## Method

Size and statement counts per unit, then distribution measures over the whole tree: concentration (what share of the code sits in the largest units), spread, and the count of outliers that dominate the estate.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `units` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `cfg` | Optional | Absent -> confidence reduced, reason recorded |
| `loc` | Optional | Absent -> confidence reduced, reason recorded |
| `comment_lines` | Optional | Absent -> confidence reduced, reason recorded |

- **Scope:** tree
- **Tier band:** 1 (size)
- **Depends on:** none
- **Direction:** `higher_is_worse`

## Why Concentration Matters

A mean hides the two 3,000-line paragraphs that are the actual migration
risk. Concentration is reported explicitly so the plan is built around the
outliers rather than the average.

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "structural_complexity",
  "sno": 7,
  "complexity": "Structural Complexity",
  "tier": "size",
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
python .claude/complexities/07_structural_complexity.py TREE.json
python .claude/complexities/07_structural_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/07_structural_complexity.py
python .claude/complexities/07_structural_complexity.py --spec
```
