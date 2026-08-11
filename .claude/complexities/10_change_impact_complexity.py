"""
Complexity #10 - Change Impact Complexity
=========================================

What is it?      How far a change to one unit can ripple through the system - its
                 blast radius.
Why needed?      It answers the question every estimate and every risk assessment
                 turns on: "if I change this, what else can break?". A unit can be
                 internally trivial and still be terrifying to touch because half
                 the system transitively depends on it.
How it works?    Merges the call graph and dependency graph into one impact graph,
                 then for each unit walks the edges BACKWARDS to find every unit
                 that can transitively reach it - that reachable set is what a
                 change to the unit can affect. The ratio of that set to the whole
                 system is the blast radius.
Input required   call_graph  (dependency_graph widens it to module-level impact)
Output artifact  Change Impact Report (uniform envelope).

LANGUAGE NEUTRALITY
    An edge A -> B means "A calls or depends on B", whatever the language. If B
    changes, everything that can reach B is at risk, so the walk is purely
    graph-theoretic and never inspects source.
"""

from __future__ import annotations

import os
import sys
from collections import deque
from typing import Any, Dict, List, Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import (  # noqa: E402
    Spec, Tree, cli_main, insufficient, level_from, result, worst,
)

SPEC = Spec(
    id="change_impact_complexity", sno=10, name="Change Impact Complexity", tier="coupling",
    requires=["call_graph"], optional=["dependency_graph", "units"],
    summary="Transitive blast radius of a change to each unit.",
)

# Share of the system reachable from a change: 5% / 15% / 30% / 50% band edges.
BANDS = (0.05, 0.15, 0.30, 0.50)


def _reverse_reach(start: str, preds: Dict[str, List[str]]) -> int:
    """Count nodes that can transitively reach `start` (impacted if it changes)."""
    seen: Set[str] = set()
    q = deque([start])
    while q:
        cur = q.popleft()
        for p in preds.get(cur, ()):  # noqa: B007
            if p not in seen:
                seen.add(p)
                q.append(p)
    seen.discard(start)
    return len(seen)


def analyze(tree_raw: Dict[str, Any]) -> Dict[str, Any]:
    tree = Tree(tree_raw)
    degraded = tree.require(SPEC)

    call = tree.raw.get("call_graph") or {}
    dep = tree.raw.get("dependency_graph") or {}
    edges = list(call.get("edges") or []) + list(dep.get("edges") or [])

    # Deterministic node set: sorted, never a raw set iterated into output.
    node_set: Set[str] = set(call.get("nodes") or []) | set(dep.get("nodes") or [])
    for e in edges:
        for side in ("from", "to"):
            if e.get(side) is not None:
                node_set.add(e[side])
    nodes = sorted(node_set)

    if not edges or len(nodes) < 2:
        insufficient("impact graph has no edges to trace reachability through")

    names = {u.get("id"): u.get("name", u.get("id")) for u in tree.units}

    preds: Dict[str, List[str]] = {n: [] for n in nodes}
    fan_out: Dict[str, int] = {n: 0 for n in nodes}
    for e in edges:
        frm, to = e.get("from"), e.get("to")
        if frm is None or to is None:
            continue
        preds.setdefault(to, []).append(frm)
        preds.setdefault(frm, preds.get(frm, []))
        fan_out[frm] = fan_out.get(frm, 0) + 1

    total = len(nodes)
    items = []
    for n in nodes:
        radius = _reverse_reach(n, preds)
        ratio = radius / (total - 1) if total > 1 else 0.0
        items.append({
            "unit": n,
            "name": names.get(n, n),
            "direct_callers": len(preds.get(n, ())),
            "fan_out": fan_out.get(n, 0),
            "blast_radius": radius,
            "impact_ratio": round(ratio, 3),
            "score": round(ratio, 3),
            "level": level_from(ratio, BANDS),
        })

    items.sort(key=lambda i: (-i["blast_radius"], i["unit"]))
    max_ratio = max(i["impact_ratio"] for i in items)
    high_impact = [i for i in items if i["impact_ratio"] >= 0.30]

    return result(
        SPEC, tree,
        level=worst(i["level"] for i in items),
        score=max_ratio,
        headline=(f"{total} component(s); {len(high_impact)} high-impact; "
                  f"worst change reaches {int(max_ratio * 100)}% of the system"),
        metrics={
            "components": total,
            "edges": len(edges),
            "max_impact_ratio": max_ratio,
            "avg_impact_ratio": round(sum(i["impact_ratio"] for i in items) / len(items), 3),
            "high_impact_components": len(high_impact),
            "bands_applied": list(BANDS),
        },
        confidence=1.0 if not degraded else 0.9,
        confidence_reasons=(
            ["dependency_graph absent - impact is traced through the call graph only, "
             "so cross-module (non-call) ripple is not counted"]
            if "dependency_graph" in degraded else []),
        hotspots=items[:10],
        items=items,
        extra={"interpretation": (
            "impact_ratio is the share of the system that transitively depends on a "
            "unit. It is the regression-test surface of any change to that unit, and "
            "the reason a one-line edit can require a full regression pass."
        )},
    )


if __name__ == "__main__":
    raise SystemExit(cli_main(analyze, SPEC))
