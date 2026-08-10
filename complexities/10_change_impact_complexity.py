"""
Complexity #10 - Change Impact Complexity
=========================================

What is it?      Measures how widely a change to one component can ripple through
                 the system  ("blast radius").
Why needed?      Estimates change risk, regression scope and modernization effort:
                 answers "if I change this, what else can break?".
How it works?    Uses the caller/callee (call graph) and dependency graph to
                 compute, for each unit, the set of components that transitively
                 depend on it (reverse reachability) = its impact set.
Input required   Call graph + dependency graph.
Output artifact  Change Impact Report (returned as a dict).

--------------------------------------------------------------------------------
INPUT CONTRACT (subset of the Normalized Tree used here)
--------------------------------------------------------------------------------
tree = {
  "language": "java",
  "units": [ {"id","name"}, ... ],                     # optional (for names)
  "call_graph":       {"nodes":[id,...], "edges":[{"from":id,"to":id}, ...]},
  "dependency_graph": {"nodes":[id,...], "edges":[{"from":id,"to":id}, ...]},  # optional
}

An edge  A -> B  means "A calls / depends on B".  So if B changes, every node
that can reach B is potentially impacted -> we walk the graph *backwards*.
"""

from __future__ import annotations
from collections import deque
from typing import Any, Dict, List, Set

# Calibration on blast-radius ratio (share of system reachable from a change), 0-1.
_BANDS = [(0.05, "L1"), (0.15, "L2"), (0.30, "L3"), (0.50, "L4")]  # else L5


def _calibrate(ratio: float) -> str:
    for threshold, level in _BANDS:
        if ratio <= threshold:
            return level
    return "L5"


def _build_predecessors(nodes: Set[str], edges: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """preds[B] = list of nodes A such that A -> B (A depends on B)."""
    preds: Dict[str, List[str]] = {n: [] for n in nodes}
    for e in edges:
        frm, to = e.get("from"), e.get("to")
        if frm is None or to is None:
            continue
        preds.setdefault(to, []).append(frm)
        preds.setdefault(frm, [])
    return preds


def _reverse_reach(start: str, preds: Dict[str, List[str]]) -> Set[str]:
    """All nodes that can transitively reach `start` (i.e. are impacted if it changes)."""
    seen: Set[str] = set()
    q = deque([start])
    while q:
        cur = q.popleft()
        for p in preds.get(cur, []):
            if p not in seen:
                seen.add(p)
                q.append(p)
    seen.discard(start)
    return seen


def analyze(tree: Dict[str, Any]) -> Dict[str, Any]:
    call = tree.get("call_graph", {}) or {}
    dep = tree.get("dependency_graph", {}) or {}

    # Merge call graph + dependency graph into one impact graph.
    edges = list(call.get("edges", []) or []) + list(dep.get("edges", []) or [])
    nodes: Set[str] = set(call.get("nodes", []) or []) | set(dep.get("nodes", []) or [])
    for e in edges:
        nodes.add(e.get("from"))
        nodes.add(e.get("to"))
    nodes.discard(None)

    names = {u["id"]: u.get("name", u["id"]) for u in tree.get("units", [])}

    total = len(nodes)
    preds = _build_predecessors(nodes, edges)

    fan_in = {n: len(preds.get(n, [])) for n in nodes}
    fan_out: Dict[str, int] = {n: 0 for n in nodes}
    for e in edges:
        if e.get("from") is not None:
            fan_out[e["from"]] = fan_out.get(e["from"], 0) + 1

    items = []
    for n in nodes:
        impacted = _reverse_reach(n, preds)
        radius = len(impacted)
        ratio = (radius / (total - 1)) if total > 1 else 0.0
        items.append({
            "unit": n,
            "name": names.get(n, n),
            "direct_callers": fan_in.get(n, 0),
            "fan_out": fan_out.get(n, 0),
            "blast_radius": radius,
            "impact_ratio": round(ratio, 3),
            "level": _calibrate(ratio),
        })

    items.sort(key=lambda i: i["blast_radius"], reverse=True)

    if items:
        max_ratio = items[0]["impact_ratio"]
        avg_ratio = round(sum(i["impact_ratio"] for i in items) / len(items), 3)
        overall = _calibrate(max_ratio)
    else:
        max_ratio = avg_ratio = 0.0
        overall = "L1"

    high_impact = [i for i in items if i["impact_ratio"] >= 0.30]

    return {
        "complexity": "Change Impact Complexity",
        "sno": 10,
        "language": tree.get("language", "unknown"),
        "summary": {
            "level": overall,
            "score": max_ratio,
            "headline": (f"{len(high_impact)} high-impact component(s); "
                         f"worst change touches {int(max_ratio * 100)}% of the system"),
        },
        "metrics": {
            "components": total,
            "edges": len(edges),
            "max_impact_ratio": max_ratio,
            "avg_impact_ratio": avg_ratio,
            "high_impact_components": len(high_impact),
        },
        "hotspots": items[:10],
        "items": items,
    }


if __name__ == "__main__":
    import json
    demo = {
        "language": "java",
        "units": [{"id": "util.log", "name": "log"}, {"id": "svc.pay", "name": "pay"},
                  {"id": "web.checkout", "name": "checkout"}],
        "call_graph": {
            "nodes": ["util.log", "svc.pay", "web.checkout"],
            "edges": [
                {"from": "web.checkout", "to": "svc.pay"},
                {"from": "svc.pay", "to": "util.log"},
                {"from": "web.checkout", "to": "util.log"},
            ],
        },
        "dependency_graph": {"nodes": [], "edges": []},
    }
    print(json.dumps(analyze(demo), indent=2))
