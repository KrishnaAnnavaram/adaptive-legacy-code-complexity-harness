---
name: dependency-complexity
description: >
  Measures internal, external, library, API, DB and platform dependencies of
  the codebase. Dependencies are a major driver of migration / modernization
  effort and upgrade risk.
  Implemented deterministically by `.claude/scripts/09_dependency_complexity.py`; used by the Complexity Agent (1_complexity) in tier band 4 (coupling).
---

# 09 - Dependency Complexity

## Purpose

**What it measures.** Measures internal, external, library, API, DB and platform dependencies of the codebase.

**Why it matters.** Dependencies are a major driver of migration / modernization effort and upgrade risk.

## Method

Reads the dependency graph, classifies each edge, computes fan-in / fan-out per module, detects dependency cycles, and measures how deep the dependency chains run.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `dependency_graph` | **Required** | Absent -> `insufficient_input`, analyzer never runs |

- **Scope:** unit
- **Tier band:** 4 (coupling)
- **Depends on:** none
- **Direction:** `higher_is_worse`

### Tree fields consumed

```
tree = {
  "language": "java",
  "dependency_graph": {
      "nodes": [module_id, ...],
      "edges": [ {"from":module_id, "to":module_id,
                  "kind":"internal|external|library|api|db|platform|config"}, ... ]
  }
}
```

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "dependency_complexity",
  "sno": 9,
  "complexity": "Dependency Complexity",
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
python .claude/scripts/09_dependency_complexity.py TREE.json
python .claude/scripts/09_dependency_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/scripts/09_dependency_complexity.py
python .claude/scripts/09_dependency_complexity.py --spec
```
