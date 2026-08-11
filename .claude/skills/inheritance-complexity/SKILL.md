---
name: inheritance-complexity
description: >
  Complexity introduced by inheritance hierarchies. Deep or wide inheritance
  makes behavior hard to trace (you must follow the chain to know what a
  class actually does).
  Implemented deterministically by `.claude/complexities/13_inheritance_complexity.py`; used by the Complexity Agent (1_complexity) in tier band 4 (coupling).
---

# 13 - Inheritance Complexity

## Purpose

**What it measures.** Complexity introduced by inheritance hierarchies.

**Why it matters.** Deep or wide inheritance makes behavior hard to trace (you must follow the chain to know what a class actually does).

## Method

From the class hierarchy it computes classic OO metrics: * DIT  - Depth of Inheritance Tree (how far up the chain) * NOC  - Number of Children (how many classes extend it) * multiple-inheritance / interface fan-in then derives an L1-L5 level.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `types` | **Required** | Absent -> `insufficient_input`, analyzer never runs |

- **Scope:** unit
- **Tier band:** 4 (coupling)
- **Depends on:** none
- **Direction:** `higher_is_worse`

### Tree fields consumed

```
tree = {
  "language": "java",
  "types": [ {
      "id","name","kind",                # kind: class|interface|abstract
      "extends":    [type_id, ...],      # superclasses
      "implements": [type_id, ...],      # implemented interfaces
      "methods":    [unit_id, ...]       # optional; for override signal
  }, ... ]
}
```

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "inheritance_complexity",
  "sno": 13,
  "complexity": "Inheritance Complexity",
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
python .claude/complexities/13_inheritance_complexity.py TREE.json
python .claude/complexities/13_inheritance_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/13_inheritance_complexity.py
python .claude/complexities/13_inheritance_complexity.py --spec
```
