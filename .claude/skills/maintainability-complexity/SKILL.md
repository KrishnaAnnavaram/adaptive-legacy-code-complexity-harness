---
name: maintainability-complexity
description: >
  Overall difficulty of maintaining the code over time. Supports takeover,
  modernization and technical-debt assessment.
  Implemented deterministically by `.claude/complexities/11_maintainability_complexity.py`; used by the Complexity Agent (1_complexity) in tier band 6 (composite).
---

# 11 - Maintainability Complexity

> **What it is** — Overall difficulty of maintaining the code over time.
> **When to use it** — Supports takeover, modernization and technical-debt assessment.
> **How it works** — Combines size (LOC), logic complexity (cyclomatic), Halstead volume and comment density into the industry Maintainability Index (MI), then derives an L1-L5 level.

## Purpose

**What it measures.** Overall difficulty of maintaining the code over time.

**Why it matters.** Supports takeover, modernization and technical-debt assessment.

## Method

Combines size (LOC), logic complexity (cyclomatic), Halstead volume and comment density into the industry Maintainability Index (MI), then derives an L1-L5 level.  Derived transparently from underlying metrics - not invented.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `units` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `cfg` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `loc` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `halstead` | Optional | Absent -> confidence reduced, reason recorded |
| `comment_lines` | Optional | Absent -> confidence reduced, reason recorded |

- **Scope:** unit
- **Tier band:** 6 (composite)
- **Depends on:** #1, #7
- **Direction:** `lower_is_worse`

### Tree fields consumed

```
tree = {
  "language": "java",
  "units": [ {
       "id","name","loc",
       "cfg": {"node_type","children":[...]},        # for cyclomatic complexity
       "halstead": {"volume": float},                # optional; estimated if absent
       "comment_lines": int                          # optional
  }, ... ]
}

Maintainability Index (Microsoft / SEI variant, clamped to 0-100):
    MI = MAX(0, (171 - 5.2*ln(V) - 0.23*CC - 16.2*ln(LOC)) * 100 / 171)
where V = Halstead volume, CC = cyclomatic complexity, LOC = lines of code.
A comment-density bonus is added (SEI extension).  Higher MI = easier to maintain.
```

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "maintainability_complexity",
  "sno": 11,
  "complexity": "Maintainability Complexity",
  "tier": "composite",
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
| An upstream report is missing | `warning` | Derive what is possible from the tree; list the gap in `derivation.estimated` |
| Tree contains no units | - | Return `insufficient_input` |
| Unhandled exception | `error` | Caught by `_core.run()`, returned as `status: error` with the exception text. The pipeline continues. |

## Invocation

```bash
python .claude/complexities/11_maintainability_complexity.py TREE.json
python .claude/complexities/11_maintainability_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/11_maintainability_complexity.py
python .claude/complexities/11_maintainability_complexity.py --spec
```
