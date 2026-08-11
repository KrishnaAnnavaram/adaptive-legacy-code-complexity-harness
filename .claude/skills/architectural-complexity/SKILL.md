---
name: architectural-complexity
description: >
  Structural quality of the system ABOVE the unit: how modules depend on
  each other, whether layers hold, and where the seams are. Every other
  analyzer scores units. None of them answers the question a modernization
  programme actually starts with: can this be decomposed, and where do we
  cut? A codebase of clean units can still be architecturally unsplittable,
  and a codebase of ugly units can decompose cleanly along good module
  lines.
  Implemented deterministically by `.claude/complexities/20_architectural_complexity.py`; used by the Complexity Agent (1_complexity) in tier band 4 (coupling).
---

# 20 - Architectural Complexity

> **What it is** — Structural quality of the system ABOVE the unit: how modules depend on each other, whether layers hold, and where the seams are.
> **When to use it** — Use it when deciding whether a system can be decomposed at all, and where the seams are.
> **How it works** — Scores four independent signals: dependency cycles, Martin instability/abstractness zones, layering violations, and hub units.

## Purpose

**What it measures.** Structural quality of the system ABOVE the unit: how modules depend on each other, whether layers hold, and where the seams are.

**Why it matters.** Every other analyzer scores units. None of them answers the question a modernization programme actually starts with: can this be decomposed, and where do we cut? A codebase of clean units can still be architecturally unsplittable, and a codebase of ugly units can decompose cleanly along good module lines.

## Method

Four independent structural signals, each with a different remedy: 1. DEPENDENCY CYCLES - modules that cannot be extracted separately, at any cost, until the cycle is broken. 2. INSTABILITY / ABSTRACTNESS (Martin) - modules in the "zone of pain" (concrete and heavily depended upon) and the "zone of uselessness" (abstract and depended on by nobody). 3. LAYERING VIOLATIONS - edges that skip or invert the declared layer order. 4. GOD UNITS AND HUBS - single points that everything routes through, whose removal is a project in itself.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `dependency_graph` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `types` | Optional | Absent -> confidence reduced, reason recorded |
| `call_graph` | Optional | Absent -> confidence reduced, reason recorded |
| `layers` | Optional | Absent -> confidence reduced, reason recorded |
| `units` | Optional | Absent -> confidence reduced, reason recorded |

- **Scope:** tree
- **Tier band:** 4 (coupling)
- **Depends on:** none
- **Direction:** `higher_is_worse`

### Tree fields consumed

```
tree = {
  "language": "java",
  "units": [ {"id","name","owner_type"}, ... ],
  "types": [ {"id","name","kind":"class|interface|abstract|record"}, ... ],  # optional
  "call_graph":       {"nodes":[unit_id,...], "edges":[{"from","to"}, ...]},
  "dependency_graph": {
      "nodes": [module_id, ...],
      "edges": [ {"from":module_id,"to":module_id,
                  "kind":"internal|external|library|api|db|platform|config"}, ... ]
  },
  "layers": {"presentation":0, "service":1, "domain":2, "data":3},   # optional
  "module_layer": {"module_id": "service", ...}                       # optional
}

MARTIN'S METRICS (1994), computed per module:
    Ca = afferent coupling  - modules that depend on this one
    Ce = efferent coupling  - modules this one depends on
    I  = Ce / (Ca + Ce)     - instability,  0 = maximally stable
    A  = abstract types / total types  - abstractness
    D  = |A + I - 1|        - distance from the main sequence

    Zone of pain       : low I, low A  - concrete and widely depended upon.
                         Expensive to change, and everything breaks when you do.
    Zone of uselessness: high A, high I - abstract and nothing depends on it.
```

## Language Neutrality

"Module" is whatever the adapter says it is: a Java package, a PL/SQL
package or schema, a COBOL program or copybook group. Abstractness needs a
type system, so it is reported as null for languages without one rather
than being faked as zero - a COBOL program is not "0% abstract", the
concept does not apply.

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "architectural_complexity",
  "sno": 20,
  "complexity": "Architectural Complexity",
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
python .claude/complexities/20_architectural_complexity.py TREE.json
python .claude/complexities/20_architectural_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/20_architectural_complexity.py
python .claude/complexities/20_architectural_complexity.py --spec
```
