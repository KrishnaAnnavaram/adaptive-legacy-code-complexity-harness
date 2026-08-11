---
name: migration-complexity
description: >
  The effort and risk of moving this code to a different language, runtime
  or platform - and which migration strategy it can actually support. This
  is the question a modernization programme is funded to answer. Every other
  analyzer is an input to it. Migration effort is NOT proportional to
  complexity: a 4,000-line unit of plain nested IFs is tedious but
  mechanical, while a 200-line unit with dynamic SQL and a platform call may
  be untranslatable by any automated means. Blockers, not size, drive cost.
  Implemented deterministically by `.claude/complexities/19_migration_complexity.py`; used by the Complexity Agent (1_complexity) in tier band 6 (composite).
---

# 19 - Migration Complexity

> **What it is** — The effort and risk of moving this code to a different language, runtime or platform - and which migration strategy it can actually support.
> **When to use it** — This is the question a modernization programme is funded to answer.
> **How it works** — Scores volume (how much there is to move, which automation reduces) separately from blockers (what defeats translation entirely), then maps the pair onto a migration strategy.

## Purpose

**What it measures.** The effort and risk of moving this code to a different language, runtime or platform - and which migration strategy it can actually support.

**Why it matters.** This is the question a modernization programme is funded to answer. Every other analyzer is an input to it. Migration effort is NOT proportional to complexity: a 4,000-line unit of plain nested IFs is tedious but mechanical, while a 200-line unit with dynamic SQL and a platform call may be untranslatable by any automated means. Blockers, not size, drive cost.

## Method

Scores two things separately, because they behave differently: VOLUME   - how much there is to move. Scales linearly, is estimable, and automation reduces it. BLOCKERS - what defeats automated translation entirely. Does not scale with size, is not reduced by automation, and drives the risk. Then maps the result onto the standard migration strategies (rehost / replatform / refactor / rearchitect / rebuild), since the decision that matters is which strategy is viable, not what the score is.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `units` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `cfg` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `sql` | Optional | Absent -> confidence reduced, reason recorded |
| `platform_calls` | Optional | Absent -> confidence reduced, reason recorded |
| `dynamic_constructs` | Optional | Absent -> confidence reduced, reason recorded |
| `dependency_graph` | Optional | Absent -> confidence reduced, reason recorded |
| `conditional_compilation` | Optional | Absent -> confidence reduced, reason recorded |
| `loc` | Optional | Absent -> confidence reduced, reason recorded |

- **Scope:** unit
- **Tier band:** 6 (composite)
- **Depends on:** #3, #15, #16, #17, #20
- **Direction:** `higher_is_worse`

### Tree fields consumed

```
tree = {
  "language": "plsql",
  "target_language": "java",                     # optional, for portability notes
  "units": [ {
      "id","name","owner_type","loc",
      "cfg": {"node_type","children":[...]},
      "sql":  [ {"kind","dynamic":bool}, ... ],           # see #15
      "platform_calls": [ {"name","kind":"os|mq|screen|vendor|hardware"}, ... ],
      "dynamic_constructs": [ {"kind":"dynamic_sql|reflection|eval|alter|
                                       dynamic_dispatch|self_modifying"}, ... ],
      "conditional_compilation": [ {"flag":str}, ... ]    # see #18
  }, ... ],
  "dependency_graph": {"edges":[{"from","to","kind":"platform|external|library|db"}, ...]}
}

upstream = {                                     # ALL OPTIONAL
  "database":      <report from #15>,
  "testability":   <report from #16>,
  "runtime":       <report from #17>,
  "configuration": <report from #18>,
  "architectural": <report from #20>,
  "maintainability": <report from #11>,
}

When an upstream report is supplied its findings are used directly. When it is
absent the corresponding signal is derived from the tree where possible, and the
dimension is listed in `derivation.estimated` so the reader knows which parts of
the score rest on a full analysis and which on a fallback.

MIGRATION STRATEGY MAPPING (Gartner 5R family)
    rehost       lift and shift; code substantially unchanged
    replatform   same code, new runtime; limited targeted change
    refactor     restructure in place, keep the language
    rearchitect  significant redesign; decomposition required first
    rebuild      rewrite from requirements; translation is not viable
```

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "migration_complexity",
  "sno": 19,
  "complexity": "Migration Complexity",
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
python .claude/complexities/19_migration_complexity.py TREE.json
python .claude/complexities/19_migration_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/19_migration_complexity.py
python .claude/complexities/19_migration_complexity.py --spec
```
