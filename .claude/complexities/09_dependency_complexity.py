"""
Complexity #09 - Dependency Complexity
======================================

What is it?      The weight, kind and shape of the dependencies between modules.
Why needed?      Dependencies are the leading driver of migration and upgrade
                 effort. A module cannot be moved, replaced or upgraded ahead of
                 the things it depends on, and a dependency CYCLE cannot be moved
                 piecewise at all. Kind matters as much as count: an internal edge
                 is refactoring, a platform edge is a porting project.
How it works?    Classifies every dependency edge, computes fan-in / fan-out and
                 instability per module, detects cycles (strongly connected
                 components), and measures the longest dependency chain, then
                 blends these into one pressure score.
Input required   dependency_graph
Output artifact  Dependency Complexity Report (uniform envelope).

LANGUAGE NEUTRALITY
    A "module" is whatever the parser grouped by: a Java package, a PL/SQL
    package, a COBOL program plus its copybooks. Edge kinds (internal / external /
    library / api / db / platform / config) come from the adapter, not from any
    language rule here.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import (  # noqa: E402
    Spec, Tree, cli_main, insufficient, level_from, result,
)

SPEC = Spec(
    id="dependency_complexity", sno=9, name="Dependency Complexity", tier="coupling",
    requires=["dependency_graph"], scope="tree",
    summary="Weight, kind and shape of inter-module dependencies.",
)

BANDS = (15, 35, 55, 75)          # blended dependency-pressure score, 0-100

_KINDS = ("internal", "external", "library", "api", "db", "platform", "config")
# Edges to things outside the codebase that must be carried during a migration.
_EXTERNAL_KINDS = {"external", "library", "api", "db", "platform"}


def _scc_cycles(nodes: List[str], succ: Dict[str, List[str]]) -> List[List[str]]:
    """Strongly connected components with >1 member, plus self-loops.

    Iterative Tarjan: legacy dependency graphs are deep enough to blow Python's
    recursion limit, and a crashed analyzer reports nothing. Nodes are visited in
    sorted order so the cycle list is byte-identical across runs.
    """
    index: Dict[str, int] = {}
    low: Dict[str, int] = {}
    on_stack: Dict[str, bool] = {}
    stack: List[str] = []
    counter = [0]
    out: List[List[str]] = []

    for root in sorted(nodes):
        if root in index:
            continue
        work: List[Tuple[str, int]] = [(root, 0)]
        while work:
            node, pi = work[-1]
            if pi == 0:
                index[node] = low[node] = counter[0]
                counter[0] += 1
                stack.append(node)
                on_stack[node] = True
            recursed = False
            succs = succ.get(node, [])
            for i in range(pi, len(succs)):
                nxt = succs[i]
                work[-1] = (node, i + 1)
                if nxt not in index:
                    work.append((nxt, 0))
                    recursed = True
                    break
                if on_stack.get(nxt):
                    low[node] = min(low[node], index[nxt])
            if recursed:
                continue
            if low[node] == index[node]:
                comp: List[str] = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    comp.append(w)
                    if w == node:
                        break
                if len(comp) > 1:
                    out.append(sorted(comp))
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])

    self_loops = sorted({n for n, tos in succ.items() if n in tos})
    for n in self_loops:
        out.append([n])
    return out


def _longest_chain(nodes: List[str], succ: Dict[str, List[str]]) -> int:
    """Longest acyclic dependency path length (memoized DFS, cycle-safe)."""
    memo: Dict[str, int] = {}
    visiting: Set[str] = set()

    def depth(v: str) -> int:
        if v in memo:
            return memo[v]
        if v in visiting:                 # inside a cycle - stop, do not loop
            return 0
        visiting.add(v)
        best = 0
        for w in succ.get(v, []):
            best = max(best, 1 + depth(w))
        visiting.discard(v)
        memo[v] = best
        return best

    return max((depth(n) for n in nodes), default=0)


def analyze(tree_raw: Dict[str, Any]) -> Dict[str, Any]:
    tree = Tree(tree_raw)
    tree.require(SPEC)

    dep = tree.raw.get("dependency_graph") or {}
    edges = dep.get("edges") or []
    nodes: List[str] = list(dep.get("nodes") or [])
    seen = set(nodes)
    for e in edges:                       # ensure every referenced node exists
        for side in ("from", "to"):
            v = e.get(side)
            if v and v not in seen:
                seen.add(v)
                nodes.append(v)

    if not edges:
        insufficient("dependency_graph carries no edges")

    kind_counts = {k: 0 for k in _KINDS}
    for e in edges:
        k = (e.get("kind") or "internal").lower()
        kind_counts[k] = kind_counts.get(k, 0) + 1

    total_edges = len(edges)
    external_edges = sum(kind_counts.get(k, 0) for k in _EXTERNAL_KINDS)
    external_ratio = external_edges / total_edges if total_edges else 0.0

    succ: Dict[str, List[str]] = {n: [] for n in nodes}
    fan_in = {n: 0 for n in nodes}
    fan_out = {n: 0 for n in nodes}
    for e in edges:
        frm, to = e.get("from"), e.get("to")
        if frm is None or to is None:
            continue
        succ.setdefault(frm, []).append(to)
        fan_out[frm] = fan_out.get(frm, 0) + 1
        fan_in[to] = fan_in.get(to, 0) + 1

    items = []
    for n in sorted(nodes):
        fi, fo = fan_in.get(n, 0), fan_out.get(n, 0)
        items.append({
            "module": n,
            "fan_in": fi,
            "fan_out": fo,
            "instability": round(fo / (fi + fo), 3) if (fi + fo) else 0.0,
        })

    cycles = _scc_cycles(nodes, succ)
    longest = _longest_chain(nodes, succ)
    avg_fan_out = sum(fan_out.values()) / len(nodes) if nodes else 0.0

    score = min(100.0, (
        external_ratio * 40
        + min(avg_fan_out, 10) / 10 * 25
        + min(longest, 10) / 10 * 20
        + min(len(cycles), 5) / 5 * 15
    ))

    hotspots = sorted(items, key=lambda m: (-(m["fan_in"] + m["fan_out"]), m["module"]))[:10]

    return result(
        SPEC, tree,
        level=level_from(score, BANDS),
        score=round(score, 1),
        headline=(f"{len(nodes)} module(s); {external_edges} external dependency/ies; "
                  f"longest chain {longest}; {len(cycles)} dependency cycle(s)"),
        metrics={
            "modules": len(nodes),
            "total_dependencies": total_edges,
            "by_kind": kind_counts,
            "external_ratio": round(external_ratio, 3),
            "avg_fan_out": round(avg_fan_out, 2),
            "max_fan_in": max((m["fan_in"] for m in items), default=0),
            "max_fan_out": max((m["fan_out"] for m in items), default=0),
            "longest_chain": longest,
            "cycle_count": len(cycles),
            "bands_applied": list(BANDS),
        },
        confidence=1.0,
        hotspots=hotspots,
        items=items,
        extra={
            "cycles": [{"modules": c, "size": len(c)} for c in cycles[:10]],
            "note": (
                "Modules inside a dependency cycle cannot be extracted or migrated "
                "independently until the cycle is broken - address those first."
            ),
        },
    )


if __name__ == "__main__":
    raise SystemExit(cli_main(analyze, SPEC))
