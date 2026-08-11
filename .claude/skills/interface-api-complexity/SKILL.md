---
name: interface-api-complexity
description: >
  Complexity of the interfaces, endpoints and contracts a system exposes.
  Important for microservices and integration-heavy applications -
  wide/heavy contracts are costly to change and integrate against.
  Implemented deterministically by `.claude/complexities/14_interface_api_complexity.py`; used by the Complexity Agent (1_complexity) in tier band 4 (coupling).
---

# 14 - Interface / API Complexity

## Purpose

**What it measures.** Complexity of the interfaces, endpoints and contracts a system exposes.

**Why it matters.** Important for microservices and integration-heavy applications - wide/heavy contracts are costly to change and integrate against.

## Method

Counts exposed operations (public interface/endpoint methods), parameters per operation, distinct schemas/DTOs referenced, and upstream/downstream (api) contract edges.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `units` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `types`, `params` | **At least one** | None present -> `insufficient_input` |
| `dependency_graph` | Optional | Absent -> confidence reduced, reason recorded |

- **Scope:** unit
- **Tier band:** 4 (coupling)
- **Depends on:** none
- **Direction:** `higher_is_worse`

### Tree fields consumed

```
tree = {
  "language": "java",
  "units": [ {
      "id","name","owner_type",
      "params": [name, ...],
      "meta": {"exposed": true, "http": "POST /orders", "schemas": [dto_id,...]}  # optional
  }, ... ],
  "types": [ {"id","name","kind","methods":[unit_id,...]} ],   # kind == "interface" => exposed
  "dependency_graph": {"edges":[{"from","to","kind":"api"}, ...]}   # api = external contracts
}

An operation is treated as "exposed" if its owner type is an interface, or its
unit meta says exposed / has an http binding.
```

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "interface_api_complexity",
  "sno": 14,
  "complexity": "Interface / API Complexity",
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
python .claude/complexities/14_interface_api_complexity.py TREE.json
python .claude/complexities/14_interface_api_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/14_interface_api_complexity.py
python .claude/complexities/14_interface_api_complexity.py --spec
```
