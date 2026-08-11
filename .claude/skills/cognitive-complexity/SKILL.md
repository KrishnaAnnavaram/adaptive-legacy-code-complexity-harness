---
name: cognitive-complexity
description: >
  How hard a unit is for a human to READ and hold in their head. Cyclomatic
  complexity counts paths, which is what a test suite cares about. It does
  not care where those paths sit. A flat switch with 20 arms and a 4-deep
  nest of ifs can score the same v(G), yet one is skimmable and the other is
  not. Cognitive complexity is the metric that separates them, and it is the
  one that correlates with how long a change actually takes.
  Implemented deterministically by `.claude/complexities/02_cognitive_complexity.py`; used by the Complexity Agent (1_complexity) in tier band 2 (structural).
---

# 02 - Cognitive Complexity

## Purpose

**What it measures.** How hard a unit is for a human to READ and hold in their head.

**Why it matters.** Cyclomatic complexity counts paths, which is what a test suite cares about. It does not care where those paths sit. A flat switch with 20 arms and a 4-deep nest of ifs can score the same v(G), yet one is skimmable and the other is not. Cognitive complexity is the metric that separates them, and it is the one that correlates with how long a change actually takes.

## Method

Three rules, after Campbell/SonarSource: 1. +1 for each break in the linear flow (if, loop, catch, jump) 2. +N extra where N is the current nesting depth 3. no increment for structures that do not break flow (else, and shorthand chains), because reading them costs nothing extra once the branch above is understood

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
  "id": "cognitive_complexity",
  "sno": 2,
  "complexity": "Cognitive Complexity",
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
python .claude/complexities/02_cognitive_complexity.py TREE.json
python .claude/complexities/02_cognitive_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/02_cognitive_complexity.py
python .claude/complexities/02_cognitive_complexity.py --spec
```
