"""
Complexity #17 - Runtime Complexity
===================================

What is it?      The expected cost of EXECUTING the code - its algorithmic growth
                 class and the work it does per unit of input.
Why needed?      Every other complexity here measures how hard code is to READ or
                 CHANGE. None of them predicts what happens under production
                 volume. A 12-line unit with a triple-nested loop over a query is
                 trivially readable and will not survive a data-volume increase,
                 and legacy modernization routinely moves code onto platforms with
                 very different cost profiles.
How it works?    Derives a growth class per unit from loop-nesting depth, then
                 adjusts for what happens INSIDE those loops. Nesting depth d
                 implies O(n^d). Recursion overrides that: self-recursion inside a
                 loop, or mutual recursion in a cycle, implies exponential
                 behaviour. Expensive operations (I/O, SQL, network) inside a loop
                 are weighted far above pure computation, because a round trip
                 costs orders of magnitude more than an instruction.
Input required   Normalized Tree: cfg with loop/call/IO node types; call_graph
                 for recursion detection.
Output artifact  Runtime Complexity Report (returned as a dict).

--------------------------------------------------------------------------------
INPUT CONTRACT (subset of the Normalized Tree used here)
--------------------------------------------------------------------------------
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

GROWTH CLASSES REPORTED
    O(1)      no loops
    O(n)      one loop level
    O(n^2)    two nested levels
    O(n^3+)   three or more nested levels
    O(2^n)    recursion driving, or recursion inside a loop

NOTE ON HONESTY
    This is a STRUCTURAL estimate, not a proof. Loop nesting bounds growth from
    the syntax; it cannot see that an inner loop runs over a fixed 12-element
    array, or that a query returns one row. Every item therefore carries
    `confidence`, and units whose loops are all statically bounded are reported
    separately - a nested loop over two fixed-size arrays is O(1) in practice
    and must not be presented as a scaling risk.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple

# Calibration on the per-unit runtime score.
_BANDS = [(5, "L1"), (14, "L2"), (30, "L3"), (60, "L4")]  # else L5

_LOOP_NODES = {"FOR", "WHILE", "DO_WHILE", "LOOP", "PERFORM_UNTIL",
               "PERFORM_VARYING", "CURSOR_LOOP", "FOREACH", "UNTIL"}

# Cost per execution of an operation. The spread is deliberately wide: a
# database round trip inside a loop is not "a bit worse" than an assignment,
# it is thousands of times worse, and a flat weighting would hide the only
# finding that matters.
_OP_COST = {
    "SQL": 25.0, "EXEC_SQL": 25.0, "DB": 25.0, "QUERY": 25.0,
    "NETWORK": 30.0, "FILE": 12.0, "IO": 12.0,
    "SORT": 8.0, "SEARCH": 4.0,
    "CALL": 2.0,
}

_GROWTH_BY_DEPTH = {0: "O(1)", 1: "O(n)", 2: "O(n^2)"}


def _calibrate(score: float) -> str:
    for threshold, level in _BANDS:
        if score <= threshold:
            return level
    return "L5"


def _growth_class(depth: int, recursive: bool, recursion_in_loop: bool) -> str:
    if recursion_in_loop or (recursive and depth >= 1):
        return "O(2^n)"
    if recursive:
        return "O(2^n)" if depth >= 1 else "O(n) recursive"
    return _GROWTH_BY_DEPTH.get(depth, "O(n^3+)")


def _analyze_cfg(cfg: Dict[str, Any], unit_id: str,
                 recursive_targets: Set[str]) -> Dict[str, Any]:
    """Walk the CFG tracking loop depth, accumulating cost weighted by depth.

    Weighting by depth is the core idea: an operation at loop depth d executes
    O(n^d) times, so its contribution is multiplied accordingly. This is what
    separates "a query in this unit" from "a query per row of the outer loop".
    """
    max_depth = 0
    loop_count = 0
    unbounded_loops = 0
    bounded_loops = 0
    weighted_cost = 0.0
    ops_in_loops: Dict[str, int] = defaultdict(int)
    ops_total: Dict[str, int] = defaultdict(int)
    recursion_in_loop = False
    hot_sites: List[Dict[str, Any]] = []

    if not cfg:
        return {
            "max_loop_depth": 0, "loop_count": 0, "unbounded_loops": 0,
            "bounded_loops": 0, "weighted_cost": 0.0, "ops_in_loops": {},
            "ops_total": {}, "recursion_in_loop": False, "hot_sites": [],
        }

    stack: List[Tuple[Dict[str, Any], int]] = [(cfg, 0)]
    while stack:
        node, depth = stack.pop()
        node_type = node.get("node_type")

        deeper = depth
        if node_type in _LOOP_NODES:
            loop_count += 1
            deeper = depth + 1
            max_depth = max(max_depth, deeper)
            if node.get("bounded") is True:
                bounded_loops += 1
            else:
                unbounded_loops += 1

        if node_type in _OP_COST:
            ops_total[node_type] += 1
            # An operation at loop depth d runs O(n^d) times, so its cost is
            # amplified by depth. The base is 4 rather than 10 and is capped:
            # true O(n^d) growth would swamp the 0-60 band scale from a single
            # site and destroy all resolution between units, which makes the
            # score unreadable without making it more accurate.
            multiplier = min(4.0 ** depth, 64.0)
            cost = _OP_COST[node_type] * multiplier / 10.0
            weighted_cost += cost
            if depth > 0:
                ops_in_loops[node_type] += 1
                if _OP_COST[node_type] >= 12.0:
                    hot_sites.append({
                        "operation": node_type,
                        "loop_depth": depth,
                        "estimated_executions": f"O(n^{depth})",
                        "note": f"{node_type} executed once per iteration at nesting depth {depth}",
                    })

        if node_type == "CALL" and depth > 0:
            target = node.get("target")
            if target and target in recursive_targets:
                recursion_in_loop = True

        for child in node.get("children", []) or []:
            stack.append((child, deeper))

    return {
        "max_loop_depth": max_depth,
        "loop_count": loop_count,
        "unbounded_loops": unbounded_loops,
        "bounded_loops": bounded_loops,
        # Capped so one pathological site cannot saturate the band scale and
        # flatten every unit above it into an indistinguishable L5.
        "weighted_cost": min(weighted_cost, 80.0),
        "ops_in_loops": dict(ops_in_loops),
        "ops_total": dict(ops_total),
        "recursion_in_loop": recursion_in_loop,
        "hot_sites": hot_sites,
    }


def _find_recursive_units(edges: List[Dict[str, Any]]) -> Tuple[Set[str], List[List[str]]]:
    """Self-recursion plus mutual-recursion cycles, via iterative DFS."""
    graph: Dict[str, Set[str]] = defaultdict(set)
    for e in edges:
        graph[e.get("from")].add(e.get("to"))

    recursive: Set[str] = {n for n in graph if n in graph[n]}
    cycles: List[List[str]] = []
    seen_cycles: Set[frozenset] = set()

    color: Dict[str, int] = {}       # 0 = visiting, 1 = done

    for root in list(graph):
        if color.get(root) == 1:
            continue
        stack: List[Tuple[str, List[str]]] = [(root, [root])]
        while stack:
            node, path = stack.pop()
            if color.get(node) == 1:
                continue
            color[node] = 0
            for nxt in graph.get(node, ()):  # noqa: B007
                if nxt in path:
                    cycle = path[path.index(nxt):]
                    key = frozenset(cycle)
                    if len(cycle) > 1 and key not in seen_cycles:
                        seen_cycles.add(key)
                        cycles.append(cycle)
                        recursive.update(cycle)
                elif color.get(nxt) != 1:
                    stack.append((nxt, path + [nxt]))
            color[node] = 1

    return recursive, cycles


def analyze(tree: Dict[str, Any]) -> Dict[str, Any]:
    units = tree.get("units", []) or []
    edges = ((tree.get("call_graph") or {}).get("edges") or [])
    recursive_units, cycles = _find_recursive_units(edges)

    items: List[Dict[str, Any]] = []
    for unit in units:
        unit_id = unit.get("id")
        stats = _analyze_cfg(unit.get("cfg") or {}, unit_id, recursive_units)

        is_recursive = unit_id in recursive_units
        depth = stats["max_loop_depth"]
        growth = _growth_class(depth, is_recursive, stats["recursion_in_loop"])

        # Score: growth dominates, real work inside loops amplifies it.
        depth_score = {0: 0.0, 1: 4.0, 2: 16.0, 3: 40.0}.get(depth, 70.0)
        if is_recursive:
            depth_score += 20.0
        if stats["recursion_in_loop"]:
            depth_score += 40.0
        score = depth_score + stats["weighted_cost"]

        # A nested loop over statically-bounded ranges is O(1) in practice.
        # Reporting it as a scaling risk would be a false positive, and false
        # positives are what make a metric get ignored.
        all_bounded = (stats["loop_count"] > 0
                       and stats["unbounded_loops"] == 0)
        if all_bounded:
            score *= 0.35

        confidence = 0.85
        conf_reasons: List[str] = []
        if stats["loop_count"] and stats["bounded_loops"] == 0 \
                and stats["unbounded_loops"] == stats["loop_count"]:
            # No loop declared its boundedness - we cannot tell fixed from open.
            confidence = 0.65
            conf_reasons.append(
                "no loop carries a `bounded` flag - growth is inferred from nesting "
                "alone and may overstate units iterating fixed-size structures"
            )
        if not stats["ops_total"]:
            confidence = min(confidence, 0.70)
            conf_reasons.append(
                "CFG carries no operation-cost nodes (SQL/IO/CALL) - per-iteration "
                "work is unmeasured"
            )

        reasons: List[str] = []
        if depth >= 3:
            reasons.append(f"loop nesting depth {depth} implies {growth} growth")
        elif depth == 2:
            reasons.append(f"nested loops imply {growth} growth")
        if stats["recursion_in_loop"]:
            reasons.append("recursive call inside a loop - potentially exponential")
        elif is_recursive:
            reasons.append("recursive - termination and depth need explicit review")
        for site in stats["hot_sites"][:3]:
            reasons.append(
                f"{site['operation']} at loop depth {site['loop_depth']} "
                f"({site['estimated_executions']} round trips)"
            )
        if all_bounded:
            reasons.append("all loops statically bounded - practical cost is constant")

        items.append({
            "unit": unit_id,
            "name": unit.get("name", unit_id),
            "owner_type": unit.get("owner_type"),
            "growth_class": growth,
            "max_loop_depth": depth,
            "loop_count": stats["loop_count"],
            "unbounded_loops": stats["unbounded_loops"],
            "bounded_loops": stats["bounded_loops"],
            "all_loops_bounded": all_bounded,
            "recursive": is_recursive,
            "recursion_in_loop": stats["recursion_in_loop"],
            "operations_in_loops": stats["ops_in_loops"],
            "weighted_cost": round(stats["weighted_cost"], 1),
            "hot_sites": stats["hot_sites"][:5],
            "score": round(score, 1),
            "level": _calibrate(score),
            "confidence": round(confidence, 2),
            "confidence_reasons": conf_reasons,
            "reasons": reasons,
        })

    scores = [i["score"] for i in items]
    max_score = max(scores, default=0.0)
    overall = _calibrate(max_score)

    growth_dist: Dict[str, int] = defaultdict(int)
    for i in items:
        growth_dist[i["growth_class"]] += 1

    heavy = [i for i in items if i["level"] in ("L4", "L5")]
    io_in_loops = [i for i in items if any(
        op in i["operations_in_loops"]
        for op in ("SQL", "EXEC_SQL", "DB", "QUERY", "NETWORK", "FILE", "IO")
    )]

    return {
        "complexity": "Runtime Complexity",
        "sno": 17,
        "language": tree.get("language", "unknown"),
        "summary": {
            "level": overall,
            "score": round(max_score, 1),
            "headline": (
                f"{len(items)} unit(s); "
                f"{growth_dist.get('O(n^2)', 0) + growth_dist.get('O(n^3+)', 0)} "
                f"super-linear; {len(io_in_loops)} with I/O or SQL inside a loop; "
                f"{len(recursive_units)} recursive"
            ),
        },
        "metrics": {
            "units": len(items),
            "growth_distribution": dict(growth_dist),
            "max_loop_depth": max((i["max_loop_depth"] for i in items), default=0),
            "recursive_units": len(recursive_units),
            "mutual_recursion_cycles": len(cycles),
            "units_with_io_in_loops": len(io_in_loops),
            "units_all_loops_bounded": len([i for i in items if i["all_loops_bounded"]]),
            "max_runtime_score": round(max_score, 1),
            "avg_runtime_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "mean_confidence": round(
                sum(i["confidence"] for i in items) / len(items), 2) if items else 0.0,
        },
        "recursion_cycles": [{"cycle": c, "length": len(c)} for c in cycles[:10]],
        "caveat": (
            "Growth classes are STRUCTURAL estimates derived from loop nesting, not "
            "proofs. Nesting bounds growth from syntax; it cannot see that an inner "
            "loop runs over a fixed 12-element table. Read `confidence` and "
            "`all_loops_bounded` before treating any item as a scaling risk."
        ),
        "hotspots": sorted(heavy, key=lambda i: -i["score"])[:10],
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
    id='runtime_complexity',
    sno=17,
    name='Runtime Complexity',
    tier='structural',
    requires=['units', 'cfg'],
    optional=['call_graph'],
    summary='Algorithmic growth class from loop nesting and per-iteration work.'
)

if __name__ == "__main__":
    raise SystemExit(_cli_main(analyze, SPEC))
