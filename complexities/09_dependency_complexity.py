"""
Complexity #9 - Dependency Complexity
=====================================

What is it?      Measures internal, external, library, API, DB and platform
                 dependencies of the codebase.
Why needed?      Dependencies are a major driver of migration / modernization
                 effort and upgrade risk.
How it works?    Reads the dependency graph, classifies each edge, computes
                 fan-in / fan-out per module, detects dependency cycles, and
                 measures how deep the dependency chains run.
Input required   Dependency graph (from parser output + build files + config).
Output artifact  Dependency Complexity Report (returned as a dict).

--------------------------------------------------------------------------------
INPUT CONTRACT (subset of the Normalized Tree used here)
--------------------------------------------------------------------------------
tree = {
  "language": "java",
  "dependency_graph": {
      "nodes": [module_id, ...],
      "edges": [ {"from":module_id, "to":module_id,
                  "kind":"internal|external|library|api|db|platform|config"}, ... ]
  }
}
"""

from __future__ import annotations
from typing import Any, Dict, List, Set

_KINDS = ["internal", "external", "library", "api", "db", "platform", "config"]
# Edges to things outside the codebase you must carry during a migration.
_EXTERNAL_KINDS = {"external", "library", "api", "db", "platform"}

# Calibration on a blended dependency-pressure score (0-100).
_BANDS = [(15, "L1"), (35, "L2"), (55, "L3"), (75, "L4")]  # else L5


def _calibrate(score: float) -> str:
    for threshold, level in _BANDS:
        if score <= threshold:
            return level
    return "L5"


def _find_cycles(nodes: List[str], succ: Dict[str, List[str]]) -> List[List[str]]:
    """Tarjan's strongly-connected-components; SCC with >1 node (or a self-loop) = cycle."""
    index: Dict[str, int] = {}
    low: Dict[str, int] = {}
    on_stack: Set[str] = set()
    stack: List[str] = []
    counter = [0]
    sccs: List[List[str]] = []

    def strongconnect(v: str) -> None:
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in succ.get(v, []):
            if w not in index:
                strongconnect(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.append(w)
                if w == v:
                    break
            sccs.append(comp)

    import sys
    sys.setrecursionlimit(max(10000, len(nodes) * 4 + 100))
    for v in nodes:
        if v not in index:
            strongconnect(v)

    cyclic = [c for c in sccs if len(c) > 1]
    self_loops = {e_from for e_from, tos in succ.items() if e_from in tos}
    for node in self_loops:
        cyclic.append([node])
    return cyclic


def _longest_chain(nodes: List[str], succ: Dict[str, List[str]]) -> int:
    """Longest dependency path length (memoized DFS; cycle-safe)."""
    memo: Dict[str, int] = {}
    visiting: Set[str] = set()

    def depth(v: str) -> int:
        if v in memo:
            return memo[v]
        if v in visiting:      # part of a cycle -> stop counting to avoid infinite loop
            return 0
        visiting.add(v)
        best = 0
        for w in succ.get(v, []):
            best = max(best, 1 + depth(w))
        visiting.discard(v)
        memo[v] = best
        return best

    return max((depth(n) for n in nodes), default=0)


def analyze(tree: Dict[str, Any]) -> Dict[str, Any]:
    dep = tree.get("dependency_graph", {}) or {}
    edges = dep.get("edges", []) or []
    nodes = list(dep.get("nodes", []) or [])

    # Make sure every referenced node exists.
    for e in edges:
        for side in ("from", "to"):
            if e.get(side) and e[side] not in nodes:
                nodes.append(e[side])

    # --- classify edges ------------------------------------------------------ #
    kind_counts = {k: 0 for k in _KINDS}
    for e in edges:
        kind_counts[e.get("kind", "internal")] = kind_counts.get(e.get("kind", "internal"), 0) + 1

    total_edges = len(edges)
    external_edges = sum(kind_counts[k] for k in _EXTERNAL_KINDS)
    external_ratio = (external_edges / total_edges) if total_edges else 0.0

    # --- fan-in / fan-out ---------------------------------------------------- #
    succ: Dict[str, List[str]] = {n: [] for n in nodes}
    fan_in = {n: 0 for n in nodes}
    fan_out = {n: 0 for n in nodes}
    for e in edges:
        succ.setdefault(e["from"], []).append(e["to"])
        fan_out[e["from"]] = fan_out.get(e["from"], 0) + 1
        fan_in[e["to"]] = fan_in.get(e["to"], 0) + 1

    per_module = [
        {"module": n, "fan_in": fan_in.get(n, 0), "fan_out": fan_out.get(n, 0),
         "instability": round(fan_out.get(n, 0) / (fan_in.get(n, 0) + fan_out.get(n, 0)), 3)
         if (fan_in.get(n, 0) + fan_out.get(n, 0)) else 0.0}
        for n in nodes
    ]

    cycles = _find_cycles(nodes, succ)
    longest = _longest_chain(nodes, succ)

    # --- blended dependency-pressure score (0-100) --------------------------- #
    avg_fan_out = (sum(fan_out.values()) / len(nodes)) if nodes else 0.0
    score = min(100.0, (
        external_ratio * 40 +
        min(avg_fan_out, 10) / 10 * 25 +
        min(longest, 10) / 10 * 20 +
        min(len(cycles), 5) / 5 * 15
    ))

    hotspots = sorted(per_module, key=lambda m: m["fan_out"] + m["fan_in"], reverse=True)[:10]

    return {
        "complexity": "Dependency Complexity",
        "sno": 9,
        "language": tree.get("language", "unknown"),
        "summary": {
            "level": _calibrate(score),
            "score": round(score, 1),
            "headline": (f"{len(nodes)} modules, {external_edges} external deps, "
                         f"{len(cycles)} dependency cycle(s)"),
        },
        "metrics": {
            "modules": len(nodes),
            "total_dependencies": total_edges,
            "by_kind": kind_counts,
            "external_ratio": round(external_ratio, 3),
            "avg_fan_out": round(avg_fan_out, 2),
            "longest_chain": longest,
            "cycle_count": len(cycles),
        },
        "cycles": cycles,
        "hotspots": hotspots,
        "items": per_module,
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
    id='dependency_complexity',
    sno=9,
    name='Dependency Complexity',
    tier='coupling',
    requires=['dependency_graph'],
    summary='Weight and kind of inter-module dependencies.'
)

if __name__ == "__main__":
    raise SystemExit(_cli_main(analyze, SPEC))
