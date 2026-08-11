"""
Complexity #15 - Database Complexity
====================================

What is it?      How hard the code's relationship with persistent data is to
                 understand, change and migrate.
Why needed?      In legacy estates the database is usually the real architecture.
                 Business rules live in SQL, transaction boundaries are implicit,
                 and schema coupling - not branch count - decides whether a unit
                 can be moved. Control-flow metrics are blind to all of it.
How it works?    Scores five independent dimensions per unit: SQL surface (how
                 much and how varied), schema reach (how many tables), statement
                 shape (joins/subqueries), dynamic SQL (what defeats static
                 analysis), and transaction control. Then adds the access-pattern
                 penalties that actually hurt at runtime - chiefly SQL executed
                 inside a loop.
Input required   Normalized Tree with per-unit sql[] statements; cfg for loop
                 nesting; dependency_graph edges of kind "db".
Output artifact  Database Complexity Report (returned as a dict).

--------------------------------------------------------------------------------
INPUT CONTRACT (subset of the Normalized Tree used here)
--------------------------------------------------------------------------------
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

LANGUAGE NEUTRALITY
    The analyzer never sees SQL text or a dialect. An adapter maps whatever the
    parser produced onto `sql[]`:
        PL/SQL   native SQL statements, EXECUTE IMMEDIATE -> dynamic: true
        COBOL    EXEC SQL ... END-EXEC blocks
        Java     JDBC execute*/prepareStatement, ORM query annotations
    Any language that reaches a database can be scored by the same rules.

CFG node types consumed (same vocabulary as #11/#12):
    FOR, WHILE, DO_WHILE, LOOP  -> loop nesting
    SQL                          -> a SQL statement site (optional; enables N+1)
    CALL                         -> callee invocation
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List

# Calibration on the per-unit weighted database score.
_BANDS = [(8, "L1"), (18, "L2"), (32, "L3"), (55, "L4")]  # else L5

_LOOP_NODES = {"FOR", "WHILE", "DO_WHILE", "LOOP", "PERFORM_UNTIL", "CURSOR_LOOP"}
_SQL_NODES = {"SQL", "EXEC_SQL", "QUERY", "SELECT", "INSERT", "UPDATE", "DELETE", "MERGE"}

# Per-statement base cost. Writes cost more than reads because they carry
# transactional and referential consequences; DDL costs most because it usually
# commits implicitly and cannot be replayed.
_KIND_WEIGHT = {
    "select": 1.0,
    "call": 1.0,
    "insert": 1.5,
    "update": 2.0,
    "delete": 2.0,
    "merge": 3.0,
    "ddl": 4.0,
    "unknown": 1.5,
}

_WRITE_KINDS = {"insert", "update", "delete", "merge", "ddl"}


def _calibrate(score: float) -> str:
    for threshold, level in _BANDS:
        if score <= threshold:
            return level
    return "L5"


def _sql_in_loops(cfg: Dict[str, Any]) -> int:
    """Count SQL sites that sit inside at least one loop.

    This is the N+1 access pattern: a query issued once per iteration. It is
    the highest-value database finding available from static structure, because
    it is invisible to every control-flow metric (the loop counts as one
    decision point whether it wraps a query or an assignment) and it is the
    defect most likely to survive a migration and only surface under load.

    Returns 0 when the parser did not mark SQL sites in the CFG - absence of
    the marker is not evidence of absence, and the caller lowers confidence
    rather than reporting a clean zero.
    """
    if not cfg:
        return 0
    found = 0
    stack: List[tuple] = [(cfg, 0)]
    while stack:
        node, depth = stack.pop()
        node_type = node.get("node_type")
        if depth > 0 and node_type in _SQL_NODES:
            found += 1
        deeper = depth + 1 if node_type in _LOOP_NODES else depth
        for child in node.get("children", []) or []:
            stack.append((child, deeper))
    return found


def _has_sql_markers(cfg: Dict[str, Any]) -> bool:
    if not cfg:
        return False
    stack = [cfg]
    while stack:
        node = stack.pop()
        if node.get("node_type") in _SQL_NODES:
            return True
        stack.extend(node.get("children", []) or [])
    return False


def _score_unit(unit: Dict[str, Any]) -> Dict[str, Any]:
    statements = unit.get("sql", []) or []
    cursors = unit.get("cursors", []) or []
    transactions = unit.get("transactions", []) or []
    cfg = unit.get("cfg") or {}

    tables: set = set()
    kinds: Counter = Counter()
    joins = subqueries = dynamic = 0
    surface = 0.0

    for stmt in statements:
        kind = (stmt.get("kind") or "unknown").lower()
        kinds[kind] += 1
        surface += _KIND_WEIGHT.get(kind, 1.5)
        for table in stmt.get("tables", []) or []:
            tables.add(str(table).upper())
        joins += int(stmt.get("joins", 0) or 0)
        subqueries += int(stmt.get("subqueries", 0) or 0)
        if stmt.get("dynamic"):
            dynamic += 1

    # -- the five dimensions ------------------------------------------------
    # Kept separate rather than folded into one number, so a reader can see
    # WHICH kind of database difficulty a unit has. A unit with 40 simple
    # single-table reads and a unit with 3 dynamic multi-table merges can score
    # similarly overall and need completely different migration treatment.
    d_surface = surface
    d_schema = len(tables) * 1.5
    d_shape = joins * 0.75 + subqueries * 1.25
    d_dynamic = dynamic * 5.0            # defeats static lineage entirely
    d_txn = 0.0
    for txn in transactions:
        kind = (txn.get("kind") or "").lower()
        d_txn += 4.0 if kind == "autonomous" else 2.0

    explicit_cursors = [c for c in cursors if c.get("explicit", True)]
    unclosed = [c for c in explicit_cursors if c.get("closed") is False]
    d_cursor = len(explicit_cursors) * 1.5 + len(unclosed) * 4.0

    n_plus_one = _sql_in_loops(cfg)
    d_pattern = n_plus_one * 6.0         # per-iteration round trip

    score = d_surface + d_schema + d_shape + d_dynamic + d_txn + d_cursor + d_pattern

    reasons: List[str] = []
    if n_plus_one:
        reasons.append(f"{n_plus_one} SQL statement(s) inside a loop (N+1 access pattern)")
    if dynamic:
        reasons.append(f"{dynamic} dynamic SQL statement(s) - data lineage not statically resolvable")
    if len(tables) >= 5:
        reasons.append(f"reaches {len(tables)} tables")
    if unclosed:
        reasons.append(f"{len(unclosed)} cursor(s) with no matching close")
    if any((t.get('kind') or '').lower() == "autonomous" for t in transactions):
        reasons.append("autonomous transaction - commits independently of the caller")
    if kinds.get("ddl"):
        reasons.append(f"{kinds['ddl']} DDL statement(s) - implicit commit")

    return {
        "unit": unit.get("id"),
        "name": unit.get("name", unit.get("id")),
        "owner_type": unit.get("owner_type"),
        "statements": len(statements),
        "tables": sorted(tables),
        "table_count": len(tables),
        "reads": sum(v for k, v in kinds.items() if k not in _WRITE_KINDS),
        "writes": sum(v for k, v in kinds.items() if k in _WRITE_KINDS),
        "joins": joins,
        "subqueries": subqueries,
        "dynamic_sql": dynamic,
        "explicit_cursors": len(explicit_cursors),
        "unclosed_cursors": len(unclosed),
        "transaction_statements": len(transactions),
        "sql_in_loop": n_plus_one,
        "dimensions": {
            "sql_surface": round(d_surface, 1),
            "schema_reach": round(d_schema, 1),
            "statement_shape": round(d_shape, 1),
            "dynamic_sql": round(d_dynamic, 1),
            "transaction_control": round(d_txn, 1),
            "cursor_management": round(d_cursor, 1),
            "access_pattern": round(d_pattern, 1),
        },
        "score": round(score, 1),
        "level": _calibrate(score),
        "reasons": reasons,
    }


def analyze(tree: Dict[str, Any]) -> Dict[str, Any]:
    units = tree.get("units", []) or []
    items = [_score_unit(u) for u in units if (u.get("sql") or u.get("cursors")
                                               or u.get("transactions"))]

    # Schema coupling: a table written by many units is a shared-ownership
    # hotspot - the thing that makes a unit impossible to extract on its own.
    writers: Dict[str, set] = defaultdict(set)
    readers: Dict[str, set] = defaultdict(set)
    for unit in units:
        for stmt in unit.get("sql", []) or []:
            kind = (stmt.get("kind") or "unknown").lower()
            target = writers if kind in _WRITE_KINDS else readers
            for table in stmt.get("tables", []) or []:
                target[str(table).upper()].add(unit.get("id"))

    shared_write_tables = {t: sorted(u) for t, u in writers.items() if len(u) > 1}
    all_tables = set(writers) | set(readers)

    db_edges = [
        e for e in ((tree.get("dependency_graph") or {}).get("edges") or [])
        if (e.get("kind") or "").lower() == "db"
    ]

    scores = [i["score"] for i in items]
    max_score = max(scores, default=0.0)
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    overall = _calibrate(max_score)

    heavy = sorted(items, key=lambda i: -i["score"])
    heavy = [i for i in heavy if i["level"] in ("L4", "L5")]

    total_dynamic = sum(i["dynamic_sql"] for i in items)
    total_n_plus_one = sum(i["sql_in_loop"] for i in items)

    # Honest confidence: the N+1 signal only exists if the parser marked SQL
    # sites in the CFG. Reporting "0 N+1 patterns" from a tree that could never
    # have shown one would be a fabricated clean bill of health.
    cfg_carries_sql = any(_has_sql_markers(u.get("cfg") or {}) for u in units)
    caveats: List[str] = []
    if items and not cfg_carries_sql:
        caveats.append(
            "CFG carries no SQL node markers - loop-embedded SQL (N+1) could not "
            "be detected. Absence of the finding is not evidence of its absence."
        )
    if items and not any(i["tables"] for i in items):
        caveats.append(
            "No table names on any statement - schema reach and shared-table "
            "coupling are unmeasured."
        )

    return {
        "complexity": "Database Complexity",
        "sno": 15,
        "language": tree.get("language", "unknown"),
        "summary": {
            "level": overall,
            "score": round(max_score, 1),
            "headline": (
                f"{len(items)} database-touching unit(s) over {len(all_tables)} table(s); "
                f"{total_dynamic} dynamic statement(s); "
                f"{total_n_plus_one} loop-embedded query site(s); "
                f"{len(shared_write_tables)} table(s) written by more than one unit"
            ),
        },
        "metrics": {
            "db_units": len(items),
            "total_sql_statements": sum(i["statements"] for i in items),
            "distinct_tables": len(all_tables),
            "read_statements": sum(i["reads"] for i in items),
            "write_statements": sum(i["writes"] for i in items),
            "dynamic_sql_statements": total_dynamic,
            "sql_in_loop_sites": total_n_plus_one,
            "explicit_cursors": sum(i["explicit_cursors"] for i in items),
            "unclosed_cursors": sum(i["unclosed_cursors"] for i in items),
            "transaction_statements": sum(i["transaction_statements"] for i in items),
            "shared_write_tables": len(shared_write_tables),
            "max_database_score": round(max_score, 1),
            "avg_database_score": avg_score,
            "external_db_dependencies": len(db_edges),
        },
        "schema_coupling": {
            "shared_write_tables": shared_write_tables,
            "most_referenced_tables": [
                {"table": t, "readers": len(readers.get(t, ())), "writers": len(writers.get(t, ()))}
                for t in sorted(
                    all_tables,
                    key=lambda t: -(len(readers.get(t, ())) + len(writers.get(t, ()))),
                )[:10]
            ],
        },
        "caveats": caveats,
        "hotspots": heavy[:10],
        "items": items,
    }

# --------------------------------------------------------------------------
# Portable contract (see _core.py). SPEC lets a harness discover, gate and
# order this analyzer without hardcoding anything about it. cli_main enforces
# the declared inputs BEFORE analyze() runs, so a starved analyzer reports
# insufficient_input instead of a misleading zero.
# --------------------------------------------------------------------------
import os as _os  # noqa: E402
import sys as _sys  # noqa: E402

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

from _core import Spec as _Spec, cli_main as _cli_main  # noqa: E402

SPEC = _Spec(
    id='database_complexity',
    sno=15,
    name='Database Complexity',
    tier='hazard',
    requires=['units'],
    requires_any=['sql', 'cursors', 'transactions'],
    optional=['cfg', 'dependency_graph'],
    summary='SQL surface, schema reach, dynamic SQL and loop-embedded queries.'
)

if __name__ == "__main__":
    raise SystemExit(_cli_main(analyze, SPEC))
