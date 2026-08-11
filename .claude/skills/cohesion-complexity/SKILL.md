---
name: cohesion-complexity
description: >
  Measures how closely related the responsibilities inside a class / module
  are. Low cohesion signals mixed responsibilities and hard-to-maintain code
  (a class doing too many unrelated things).
  Implemented deterministically by `.claude/complexities/08_cohesion_complexity.py`; used by the Complexity Agent (1_complexity) in tier band 4 (coupling).
---

# 08 - Cohesion Complexity

## Purpose

**What it measures.** Measures how closely related the responsibilities inside a class / module are.

**Why it matters.** Low cohesion signals mixed responsibilities and hard-to-maintain code (a class doing too many unrelated things).

## Method

For every type (class/module) it measures how much the methods share the same fields / state.  Uses the LCOM family of metrics.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `units` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `types` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `call_graph` | Optional | Absent -> confidence reduced, reason recorded |
| `references` | Optional | Absent -> confidence reduced, reason recorded |

- **Scope:** unit
- **Tier band:** 4 (coupling)
- **Depends on:** none
- **Direction:** `higher_is_worse`

### Tree fields consumed

```
tree = {
  "language": "java",
  "units": [ { "id","name","owner_type", "references": [field_id, ...] }, ... ],
  "types": [ { "id","name","kind","fields":[field_id,...], "methods":[unit_id,...] }, ... ],
  "call_graph": { "nodes":[unit_id,...], "edges":[{"from":unit_id,"to":unit_id}, ...] },
}
Only the fields above are used by this analyzer; anything else is ignored.
```

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "cohesion_complexity",
  "sno": 8,
  "complexity": "Cohesion Complexity",
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
python .claude/complexities/08_cohesion_complexity.py TREE.json
python .claude/complexities/08_cohesion_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/08_cohesion_complexity.py
python .claude/complexities/08_cohesion_complexity.py --spec
```
