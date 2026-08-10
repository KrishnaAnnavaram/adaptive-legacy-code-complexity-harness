#!/usr/bin/env python3
"""
tree_bridge.py — convert a Style-A canonical tree into a Style-B Normalized Tree.

WHY THIS EXISTS
---------------
The analyzers in complexities/ were authored against two different, mutually
incompatible input shapes:

  STYLE A  (cyclomatic, cognitive, control_flow, coupling, nesting, npath,
            structural — the unnumbered scripts)
      A single recursive tree of {kind, label, name, start_line, end_line,
      children[]}. Lowercase canonical `kind` vocabulary. CLI-driven, writes a
      JSON artifact per file.

  STYLE B  (08–20 — the numbered scripts)
      {language, units:[{id, name, owner_type, loc, cfg:{node_type, children},
      params, references, ...}], call_graph, dependency_graph, types}.
      UPPERCASE `node_type` vocabulary, flat unit list, graphs alongside.
      Library-style: analyze(tree) -> dict.

They share no field names and no vocabulary. Feeding a Style-A tree to a Style-B
analyzer does not raise — it reports **zero units** and a clean-looking result,
which is the worst possible failure mode because nothing signals that the
analysis did not happen.

This bridge lets ONE parser output drive all twenty analyzers: produce Style A,
convert here, feed Style B.

WHAT IT CANNOT INVENT
---------------------
Style A's vocabulary has no concept of SQL statements, config reads, platform
calls, data references, or module dependencies. Those fields are required by
analyzers 12, 15, 16, 18, 19 and 20. The bridge therefore emits an explicit
`_bridge_report.missing_for` list naming which analyzers will under-report, and
never fabricates an empty list that would read as "none found".

Extended Style-A kinds (optional, recognised if your adapter emits them) let the
bridge carry those signals across: sql_select, sql_insert, sql_update,
sql_delete, sql_merge, dynamic_sql, call, io, file, network, db, platform,
goto, alter, perform_thru, config_read, literal.

Usage:
    python3 tools/tree_bridge.py tree_a.json -o tree_b.json --language cobol
    python3 tools/tree_bridge.py tree_a.json --report      # gap report only
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

CONTAINER_SCOPE_KINDS = {"program", "module", "class", "package"}
UNIT_SCOPE_KINDS = {"function", "method", "procedure", "paragraph", "section"}
SCOPE_KINDS = CONTAINER_SCOPE_KINDS | UNIT_SCOPE_KINDS

# Style-A `kind` -> Style-B `node_type`. Kinds absent here are dropped from the
# CFG (they carry no signal any Style-B analyzer consumes) but still counted in
# the bridge report.
KIND_TO_NODE_TYPE = {
    # control flow
    "if": "IF", "elif": "ELIF", "else": "ELSE",
    "for": "FOR", "foreach": "FOR", "while": "WHILE", "do_while": "DO_WHILE",
    "until": "UNTIL", "loop": "LOOP",
    "perform_until": "PERFORM_UNTIL", "perform_varying": "PERFORM_VARYING",
    "cursor_loop": "CURSOR_LOOP",
    "case_clause": "CASE", "when_clause": "CASE", "switch": "CASE",
    "default_clause": "DEFAULT",
    "catch": "CATCH", "except": "CATCH", "finally": "FINALLY",
    "ternary": "TERNARY",
    "boolean_and": "AND", "boolean_or": "OR",
    # unstructured flow — consumed by 19 (migration blockers)
    "goto": "GOTO", "alter": "ALTER", "perform_thru": "PERFORM_THRU",
    "fall_through": "FALL_THROUGH",
    # effects — consumed by 15, 16, 17, 19
    "call": "CALL",
    "sql_select": "SQL", "sql_insert": "SQL", "sql_update": "SQL",
    "sql_delete": "SQL", "sql_merge": "SQL", "exec_sql": "EXEC_SQL",
    "dynamic_sql": "SQL",
    "db": "DB", "query": "QUERY",
    "io": "IO", "file": "FILE", "network": "NETWORK",
    "screen": "SCREEN", "display": "DISPLAY",
    "platform": "PLATFORM", "system": "SYSTEM",
    "sort": "SORT", "search": "SEARCH",
    "sequence": "SEQUENCE", "block": "SEQUENCE",
}

_SQL_KINDS = {
    "sql_select": "select", "sql_insert": "insert", "sql_update": "update",
    "sql_delete": "delete", "sql_merge": "merge", "exec_sql": "unknown",
    "dynamic_sql": "unknown",
}

_LOOP_A_KINDS = {"for", "foreach", "while", "do_while", "until", "loop",
                 "perform_until", "perform_varying", "cursor_loop"}

# Style-B fields the numbered analyzers need that Style A cannot express.
_UNSUPPLIABLE = {
    "sql[].tables / joins / subqueries": [15],
    "cursors[]": [15],
    "transactions[]": [15],
    "references[] / globals[] / writes[]": [12, 16],
    "config_reads[] / feature_flags[] / literals[]": [18],
    "conditional_compilation[]": [18, 19],
    "platform_calls[]": [19],
    "types[] (kind/extends/implements)": [8, 13, 14, 20],
    "dependency_graph": [9, 10, 16, 19, 20],
}


class Bridge:
    def __init__(self, language: str):
        self.language = language
        self.units: List[Dict[str, Any]] = []
        self.call_edges: List[Dict[str, str]] = []
        self.unknown_kinds: Dict[str, int] = {}
        self.dropped_nodes = 0
        self.total_nodes = 0

    # -- CFG conversion ---------------------------------------------------

    def _to_cfg(self, node: Dict[str, Any], unit_id: str) -> Dict[str, Any]:
        self.total_nodes += 1
        kind = (node.get("kind") or "").lower()
        node_type = KIND_TO_NODE_TYPE.get(kind)

        if node_type is None:
            if kind and kind not in SCOPE_KINDS:
                self.unknown_kinds[kind] = self.unknown_kinds.get(kind, 0) + 1
                self.dropped_nodes += 1
            node_type = "SEQUENCE"

        out: Dict[str, Any] = {"node_type": node_type, "children": []}

        if node.get("start_line") is not None:
            out["line"] = node["start_line"]
        if node_type == "CALL":
            target = node.get("target") or node.get("name") or node.get("label")
            if target:
                out["target"] = target
                self.call_edges.append({"from": unit_id, "to": str(target)})
        # Style A has no way to declare a loop's trip count as statically known,
        # so `bounded` is deliberately NOT set here. Analyzer 17 reads its
        # absence as "unknown" and lowers confidence, which is correct — setting
        # it to False would assert unboundedness we have not established.

        for child in node.get("children", []) or []:
            if (child.get("kind") or "").lower() in SCOPE_KINDS:
                continue                       # nested scope becomes its own unit
            out["children"].append(self._to_cfg(child, unit_id))
        return out

    # -- SQL extraction ---------------------------------------------------

    def _collect_sql(self, node: Dict[str, Any], acc: List[Dict[str, Any]]) -> None:
        kind = (node.get("kind") or "").lower()
        if kind in _SQL_KINDS:
            entry: Dict[str, Any] = {"kind": _SQL_KINDS[kind]}
            if node.get("start_line") is not None:
                entry["line"] = node["start_line"]
            if kind == "dynamic_sql":
                entry["dynamic"] = True
            acc.append(entry)
        for child in node.get("children", []) or []:
            if (child.get("kind") or "").lower() in SCOPE_KINDS:
                continue
            self._collect_sql(child, acc)

    # -- unit discovery ---------------------------------------------------

    def walk(self, node: Dict[str, Any], owner: Optional[str] = None) -> None:
        kind = (node.get("kind") or "").lower()

        if kind in SCOPE_KINDS:
            name = node.get("name") or f"ANON_{len(self.units)}"
            unit_id = f"{owner}.{name}" if owner else str(name)

            direct_children = [
                c for c in (node.get("children") or [])
                if (c.get("kind") or "").lower() not in SCOPE_KINDS
            ]
            is_unit = kind in UNIT_SCOPE_KINDS or bool(direct_children)

            if is_unit:
                start, end = node.get("start_line"), node.get("end_line")
                loc = (end - start + 1) if (isinstance(start, int)
                                            and isinstance(end, int)) else 0
                sql: List[Dict[str, Any]] = []
                for c in direct_children:
                    self._collect_sql(c, sql)

                cfg_root = {"kind": "sequence", "children": direct_children}
                self.units.append({
                    "id": unit_id,
                    "name": str(name),
                    "owner_type": owner or "MODULE",
                    "loc": loc,
                    "start_line": start,
                    "end_line": end,
                    "cfg": self._to_cfg(cfg_root, unit_id),
                    **({"sql": sql} if sql else {}),
                })

            next_owner = str(name) if kind in CONTAINER_SCOPE_KINDS else (owner or str(name))
            for child in node.get("children") or []:
                if (child.get("kind") or "").lower() in SCOPE_KINDS:
                    self.walk(child, next_owner)
            return

        for child in node.get("children") or []:
            self.walk(child, owner)

    # -- result -----------------------------------------------------------

    def build(self, root: Dict[str, Any]) -> Dict[str, Any]:
        if (root.get("kind") or "").lower() not in SCOPE_KINDS:
            root = {"kind": "module", "name": "MODULE_LEVEL",
                    "start_line": root.get("start_line"),
                    "end_line": root.get("end_line"), "children": [root]}
        self.walk(root)

        supplied_sql = any("sql" in u for u in self.units)
        missing_for = sorted({
            sno for field, snos in _UNSUPPLIABLE.items() for sno in snos
            if not (field.startswith("sql[]") and supplied_sql)
        })

        return {
            "language": self.language,
            "units": self.units,
            "call_graph": {
                "nodes": sorted({u["id"] for u in self.units}
                                | {e["to"] for e in self.call_edges}),
                "edges": self.call_edges,
            },
            "_bridge_report": {
                "bridge_version": "1.0.0",
                "units_emitted": len(self.units),
                "call_edges": len(self.call_edges),
                "cfg_nodes_converted": self.total_nodes,
                "nodes_dropped_unknown_kind": self.dropped_nodes,
                "unknown_kinds": dict(sorted(self.unknown_kinds.items(),
                                             key=lambda kv: -kv[1])),
                "fields_style_a_cannot_express": _UNSUPPLIABLE,
                "analyzers_that_will_under_report": missing_for,
                "warning": (
                    "Style A carries no data references, dependency graph, type "
                    "system, config reads or platform calls. Analyzers listed in "
                    "`analyzers_that_will_under_report` will run without error and "
                    "return low or zero findings that reflect MISSING INPUT, not "
                    "clean code. Enrich the tree or supply those fields separately "
                    "before treating their output as a result."
                ),
            },
        }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Convert a Style-A canonical tree to a Style-B Normalized Tree")
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("--language", default="unknown")
    ap.add_argument("--report", action="store_true",
                    help="print only the gap report")
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8") as fh:
        tree_a = json.load(fh)

    result = Bridge(args.language).build(tree_a)

    if args.report:
        print(json.dumps(result["_bridge_report"], indent=2))
        return 0

    text = json.dumps(result, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
        rep = result["_bridge_report"]
        print(f"wrote {args.output}: {rep['units_emitted']} unit(s), "
              f"{rep['call_edges']} call edge(s), "
              f"{rep['nodes_dropped_unknown_kind']} node(s) dropped",
              file=sys.stderr)
        if rep["analyzers_that_will_under_report"]:
            print(f"WARNING: analyzers {rep['analyzers_that_will_under_report']} "
                  f"will under-report — Style A cannot express their inputs",
                  file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
