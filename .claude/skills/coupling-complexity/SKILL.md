---
name: coupling-complexity
description: >
  How tightly units are bound to each other. Coupling decides what you can
  move. A unit can be internally simple and still be impossible to extract
  because forty things call it. Every decomposition, service-extraction and
  strangler-fig plan is really a coupling argument.
  Implemented deterministically by `.claude/complexities/04_coupling_complexity.py`; used by the Complexity Agent (3_complexity) in tier band 4 (coupling).
---

# 04 - Coupling Complexity

> **What it is** — How tightly units are bound to each other.
> **When to use it** — Coupling decides what you can move.
> **How it works** — Fan-in (who calls me) and fan-out (who I call) per unit, then Henry & Kafura information flow, (fan_in * fan_out)^2.

## Purpose

**What it measures.** How tightly units are bound to each other.

**Why it matters.** Coupling decides what you can move. A unit can be internally simple and still be impossible to extract because forty things call it. Every decomposition, service-extraction and strangler-fig plan is really a coupling argument.

## Method

Fan-in (who calls me) and fan-out (who I call) per unit, then Henry & Kafura information flow, (fan_in * fan_out)^2. The square is the point: a unit that is both heavily called AND calls widely is a routing hub, and removing it is a project rather than a task. A unit with high fan-in but low fan-out is a leaf utility and is usually harmless.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `units` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `call_graph` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `dependency_graph` | Optional | Absent -> confidence reduced, reason recorded |

- **Scope:** unit
- **Tier band:** 4 (coupling)
- **Depends on:** none
- **Direction:** `higher_is_worse`

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "coupling_complexity",
  "sno": 4,
  "complexity": "Coupling Complexity",
  "tier": "coupling",
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
python .claude/complexities/04_coupling_complexity.py TREE.json
python .claude/complexities/04_coupling_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/04_coupling_complexity.py
python .claude/complexities/04_coupling_complexity.py --spec
```
