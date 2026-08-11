---
name: data-flow-complexity
description: >
  Measures how values and data move across statements, functions and
  modules. Reveals transformations, side effects and data dependencies that
  make code hard to reason about.
  Implemented deterministically by `.claude/scripts/12_data_flow_complexity.py`; used by the Complexity Agent (1_complexity) in tier band 3 (data).
---

# 12 - Data Flow Complexity

## Purpose

**What it measures.** Measures how values and data move across statements, functions and modules.

**Why it matters.** Reveals transformations, side effects and data dependencies that make code hard to reason about.

## Method

Builds def-use style signals per unit: how many distinct data elements it touches, how many it passes to callees, and how much shared state it reads/writes.  Aggregates per unit and per module.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `units` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `references`, `params` | **At least one** | None present -> `insufficient_input` |
| `cfg` | Optional | Absent -> confidence reduced, reason recorded |

- **Scope:** unit
- **Tier band:** 3 (data)
- **Depends on:** none
- **Direction:** `higher_is_worse`

### Tree fields consumed

```
tree = {
  "language": "java",
  "units": [ {
      "id","name","owner_type",
      "params": [name, ...],
      "references": [data_id, ...],       # variables / fields the unit reads or writes
      "cfg": {"node_type","children":[...]}   # CALL nodes = data handed to callees
  }, ... ]
}

Note: a full def-use graph needs richer parser output; this analyzer approximates
data-flow pressure from the data signals the Normalized Tree already carries.
```

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "data_flow_complexity",
  "sno": 12,
  "complexity": "Data Flow Complexity",
  "tier": "data",
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
python .claude/scripts/12_data_flow_complexity.py TREE.json
python .claude/scripts/12_data_flow_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/scripts/12_data_flow_complexity.py
python .claude/scripts/12_data_flow_complexity.py --spec
```
