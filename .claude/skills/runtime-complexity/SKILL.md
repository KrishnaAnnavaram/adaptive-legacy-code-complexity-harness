---
name: runtime-complexity
description: >
  The expected cost of EXECUTING the code - its algorithmic growth class and
  the work it does per unit of input. Every other complexity here measures
  how hard code is to READ or CHANGE. None of them predicts what happens
  under production volume. A 12-line unit with a triple-nested loop over a
  query is trivially readable and will not survive a data-volume increase,
  and legacy modernization routinely moves code onto platforms with very
  different cost profiles.
  Implemented deterministically by `.claude/complexities/17_runtime_complexity.py`; used by the Complexity Agent (1_complexity) in tier band 2 (structural).
---

# 17 - Runtime Complexity

> **What it is** — The expected cost of EXECUTING the code - its algorithmic growth class and the work it does per unit of input.
> **When to use it** — Use it before moving code to a new platform, or when production data volume is expected to grow.
> **How it works** — Derives a growth class from loop-nesting depth, then weights the work done inside those loops; recursion inside a loop implies exponential behaviour.

## Purpose

**What it measures.** The expected cost of EXECUTING the code - its algorithmic growth class and the work it does per unit of input.

**Why it matters.** Every other complexity here measures how hard code is to READ or CHANGE. None of them predicts what happens under production volume. A 12-line unit with a triple-nested loop over a query is trivially readable and will not survive a data-volume increase, and legacy modernization routinely moves code onto platforms with very different cost profiles.

## Method

Derives a growth class per unit from loop-nesting depth, then adjusts for what happens INSIDE those loops. Nesting depth d implies O(n^d). Recursion overrides that: self-recursion inside a loop, or mutual recursion in a cycle, implies exponential behaviour. Expensive operations (I/O, SQL, network) inside a loop are weighted far above pure computation, because a round trip costs orders of magnitude more than an instruction.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `units` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `cfg` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `call_graph` | Optional | Absent -> confidence reduced, reason recorded |

- **Scope:** unit
- **Tier band:** 2 (structural)
- **Depends on:** none
- **Direction:** `higher_is_worse`

### Tree fields consumed

```
tree = {
  "language": "cobol",
  "units": [ {
      "id","name","owner_type","loc",
      "cfg": { "node_type", "children":[...],
               "bounded": bool,        # optional, on loop nodes: is the trip
                                       # count statically known?
               "collection": str }     # optional: what is being iterated
  }, ... ],
  "call_graph": {"edges":[{"from":unit_id,"to":unit_id}, ...]}   # recursion
}

CFG node types consumed:
    loops    FOR, WHILE, DO_WHILE, LOOP, PERFORM_UNTIL, PERFORM_VARYING,
             CURSOR_LOOP, FOREACH, UNTIL
    cost     SQL, EXEC_SQL, DB, QUERY (very high), NETWORK, FILE, IO (high),
             CALL (medium), SORT, SEARCH (algorithmic)
```

## Growth Classes Reported

O(1)      no loops
O(n)      one loop level
O(n^2)    two nested levels
O(n^3+)   three or more nested levels
O(2^n)    recursion driving, or recursion inside a loop

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "runtime_complexity",
  "sno": 17,
  "complexity": "Runtime Complexity",
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
python .claude/complexities/17_runtime_complexity.py TREE.json
python .claude/complexities/17_runtime_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/17_runtime_complexity.py
python .claude/complexities/17_runtime_complexity.py --spec
```
