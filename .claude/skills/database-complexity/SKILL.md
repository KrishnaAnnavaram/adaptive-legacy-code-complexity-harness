---
name: database-complexity
description: >
  How hard the code's relationship with persistent data is to understand,
  change and migrate. In legacy estates the database is usually the real
  architecture. Business rules live in SQL, transaction boundaries are
  implicit, and schema coupling - not branch count - decides whether a unit
  can be moved. Control-flow metrics are blind to all of it.
  Implemented deterministically by `.claude/complexities/15_database_complexity.py`; used by the Complexity Agent (1_complexity) in tier band 5 (hazard).
---

# 15 - Database Complexity

## Purpose

**What it measures.** How hard the code's relationship with persistent data is to understand, change and migrate.

**Why it matters.** In legacy estates the database is usually the real architecture. Business rules live in SQL, transaction boundaries are implicit, and schema coupling - not branch count - decides whether a unit can be moved. Control-flow metrics are blind to all of it.

## Method

Scores five independent dimensions per unit: SQL surface (how much and how varied), schema reach (how many tables), statement shape (joins/subqueries), dynamic SQL (what defeats static analysis), and transaction control. Then adds the access-pattern penalties that actually hurt at runtime - chiefly SQL executed inside a loop.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `units` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `sql`, `cursors`, `transactions` | **At least one** | None present -> `insufficient_input` |
| `cfg` | Optional | Absent -> confidence reduced, reason recorded |
| `dependency_graph` | Optional | Absent -> confidence reduced, reason recorded |

- **Scope:** unit
- **Tier band:** 5 (hazard)
- **Depends on:** none
- **Direction:** `higher_is_worse`

### Tree fields consumed

```
tree = {
  "language": "plsql",
  "units": [ {
      "id","name","owner_type",
      "sql": [ {                              # one entry per SQL statement
          "kind":       "select|insert|update|delete|merge|ddl|call|unknown",
          "tables":     [table_name, ...],    # optional
          "joins":      int,                  # optional
          "subqueries": int,                  # optional
          "dynamic":    bool,                 # EXECUTE IMMEDIATE / sp_executesql /
                                              # string-built JDBC
          "line":       int                   # optional
      }, ... ],
      "cursors":      [ {"name","explicit":bool,"closed":bool}, ... ],  # optional
      "transactions": [ {"kind":"commit|rollback|savepoint|autonomous"}, ... ],
      "cfg": {"node_type","children":[...]}   # LOOP nesting + SQL node placement
  }, ... ],
  "dependency_graph": {"edges":[{"from","to","kind":"db"}, ...]}   # optional
}
```

## Language Neutrality

The analyzer never sees SQL text or a dialect. An adapter maps whatever the
parser produced onto `sql[]`:
    PL/SQL   native SQL statements, EXECUTE IMMEDIATE -> dynamic: true
    COBOL    EXEC SQL ... END-EXEC blocks
    Java     JDBC execute*/prepareStatement, ORM query annotations
Any language that reaches a database can be scored by the same rules.

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "database_complexity",
  "sno": 15,
  "complexity": "Database Complexity",
  "tier": "hazard",
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
python .claude/complexities/15_database_complexity.py TREE.json
python .claude/complexities/15_database_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/15_database_complexity.py
python .claude/complexities/15_database_complexity.py --spec
```
