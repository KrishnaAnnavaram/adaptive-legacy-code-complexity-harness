---
name: control-flow-complexity
description: >
  How STRUCTURED the flow is - whether it reduces to clean nested blocks, or
  contains jumps that make it irreducible. This is the metric that decides
  whether automated translation is even possible. Cyclomatic complexity
  tells you how many tests you need; this tells you whether the unit can be
  mechanically restructured at all. For COBOL, RPG and PL/I it is the single
  highest-value structural number, well above v(G).
  Implemented deterministically by `.claude/complexities/03_control_flow_complexity.py`; used by the Complexity Agent (1_complexity) in tier band 2 (structural).
---

# 03 - Control Flow Complexity

> **What it is** — How STRUCTURED the flow is - whether it reduces to clean nested blocks, or contains jumps that make it irreducible.
> **When to use it** — This is the metric that decides whether automated translation is even possible.
> **How it works** — Approximates McCabe's essential complexity.

## Purpose

**What it measures.** How STRUCTURED the flow is - whether it reduces to clean nested blocks, or contains jumps that make it irreducible.

**Why it matters.** This is the metric that decides whether automated translation is even possible. Cyclomatic complexity tells you how many tests you need; this tells you whether the unit can be mechanically restructured at all. For COBOL, RPG and PL/I it is the single highest-value structural number, well above v(G).

## Method

Approximates McCabe's essential complexity. Well-structured constructs (if/else, loops, case) reduce away and cost nothing. What remains after reduction is what makes flow irreducible: GOTO, ALTER, PERFORM THRU ranges, paragraph fall-through and multiple exit points.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `units` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `cfg` | **Required** | Absent -> `insufficient_input`, analyzer never runs |

- **Scope:** unit
- **Tier band:** 2 (structural)
- **Depends on:** none
- **Direction:** `higher_is_worse`

## Honesty Note

True ev(G) requires collapsing a real control-flow GRAPH. A tree of CFG
nodes is not a graph - it has no edges. What is computed here is therefore
an UNSTRUCTUREDNESS INDEX derived from the jump constructs present, and it
is reported under that name. It is a sound proxy and a deliberately
conservative one, but it is not ev(G) and is not labelled as such.

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "control_flow_complexity",
  "sno": 3,
  "complexity": "Control Flow Complexity",
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
python .claude/complexities/03_control_flow_complexity.py TREE.json
python .claude/complexities/03_control_flow_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/03_control_flow_complexity.py
python .claude/complexities/03_control_flow_complexity.py --spec
```
