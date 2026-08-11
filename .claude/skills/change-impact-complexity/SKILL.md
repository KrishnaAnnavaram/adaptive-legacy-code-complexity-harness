---
name: change-impact-complexity
description: >
  Measures how widely a change to one component can ripple through the
  system ("blast radius"). Estimates change risk, regression scope and
  modernization effort: answers "if I change this, what else can break?".
  Implemented deterministically by `.claude/complexities/10_change_impact_complexity.py`; used by the Complexity Agent (1_complexity) in tier band 4 (coupling).
---

# 10 - Change Impact Complexity

> **What it is** — Measures how widely a change to one component can ripple through the system ("blast radius").
> **When to use it** — Use it to size regression scope before a change - it answers 'if I touch this, what else must be retested'.
> **How it works** — Uses the caller/callee (call graph) and dependency graph to compute, for each unit, the set of components that transitively depend on it (reverse reachability) = its impact set.

## Purpose

**What it measures.** Measures how widely a change to one component can ripple through the system  ("blast radius").

**Why it matters.** Estimates change risk, regression scope and modernization effort: answers "if I change this, what else can break?".

## Method

Uses the caller/callee (call graph) and dependency graph to compute, for each unit, the set of components that transitively depend on it (reverse reachability) = its impact set.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `call_graph` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `dependency_graph` | Optional | Absent -> confidence reduced, reason recorded |
| `units` | Optional | Absent -> confidence reduced, reason recorded |

- **Scope:** unit
- **Tier band:** 4 (coupling)
- **Depends on:** none
- **Direction:** `higher_is_worse`

### Tree fields consumed

```
tree = {
  "language": "java",
  "units": [ {"id","name"}, ... ],                     # optional (for names)
  "call_graph":       {"nodes":[id,...], "edges":[{"from":id,"to":id}, ...]},
  "dependency_graph": {"nodes":[id,...], "edges":[{"from":id,"to":id}, ...]},  # optional
}

An edge  A -> B  means "A calls / depends on B".  So if B changes, every node
that can reach B is potentially impacted -> we walk the graph *backwards*.
```

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "change_impact_complexity",
  "sno": 10,
  "complexity": "Change Impact Complexity",
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
python .claude/complexities/10_change_impact_complexity.py TREE.json
python .claude/complexities/10_change_impact_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/10_change_impact_complexity.py
python .claude/complexities/10_change_impact_complexity.py --spec
```
