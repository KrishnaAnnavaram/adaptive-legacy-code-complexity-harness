"""
Complexity #12 - Data Flow Complexity
=====================================

What is it?      Measures how values and data move across statements, functions
                 and modules.
Why needed?      Reveals transformations, side effects and data dependencies that
                 make code hard to reason about.
How it works?    Builds def-use style signals per unit: how many distinct data
                 elements it touches, how many it passes to callees, and how much
                 shared state it reads/writes.  Aggregates per unit and per module.
Input required   AST + data-flow signals (references, params, CALL nodes).
Output artifact  Data Flow Complexity Report (returned as a dict).

--------------------------------------------------------------------------------
INPUT CONTRACT (subset of the Normalized Tree used here)
--------------------------------------------------------------------------------
tree = {
  "language": "java",
  "units": [ {
      "id","name","owner_type",
      "params": [name, ...],
      "references": [data_id, ...],       # variables / fields the unit reads or writes
      "cfg": {"node_type","children":[...]}   # CALL nodes = data handed to callees
  }, ... ]
}

Note: a full def-use graph needs richer parser output; this analyzer approximates
data-flow pressure from the data signals the Normalized Tree already carries.
"""

from __future__ import annotations
from collections import defaultdict
from typing import Any, Dict, List

# Calibration on per-unit data-flow score (weighted count of data interactions).
_BANDS = [(6, "L1"), (12, "L2"), (20, "L3"), (32, "L4")]  # else L5


def _calibrate(score: float) -> str:
    for threshold, level in _BANDS:
        if score <= threshold:
            return level
    return "L5"


def _count_calls(cfg: Dict[str, Any]) -> int:
    """Number of CALL nodes = points where data is passed out to other units."""
    if not cfg:
        return 0
    count = 0
    stack = [cfg]
    while stack:
        node = stack.pop()
        if node.get("node_type") == "CALL":
            count += 1
        stack.extend(node.get("children", []) or [])
    return count


def analyze(tree: Dict[str, Any]) -> Dict[str, Any]:
    units = tree.get("units", [])

    # writers[data_id] = how many units reference it -> shared/global data is costlier.
    refs_by_data: Dict[str, int] = defaultdict(int)
    for u in units:
        for r in set(u.get("references", []) or []):
            refs_by_data[r] += 1

    items: List[Dict[str, Any]] = []
    module_scores: Dict[str, float] = defaultdict(float)

    for u in units:
        params = list(u.get("params", []) or [])
        refs = list(u.get("references", []) or [])
        distinct_refs = set(refs)
        calls = _count_calls(u.get("cfg") or {})

        # Shared data (touched by >1 unit) adds extra data-coupling cost.
        shared = sum(1 for r in distinct_refs if refs_by_data[r] > 1)

        # Weighted data-flow score: inputs + data touched + outbound data + shared state.
        score = (
            len(params) * 1.0 +
            len(distinct_refs) * 1.0 +
            calls * 1.5 +
            shared * 2.0
        )
        owner = u.get("owner_type") or "<module>"
        module_scores[owner] += score

        items.append({
            "unit": u["id"],
            "name": u.get("name", u["id"]),
            "params_in": len(params),
            "data_refs": len(distinct_refs),
            "shared_data_refs": shared,
            "outbound_calls": calls,
            "data_flow_score": round(score, 1),
            "level": _calibrate(score),
        })

    items.sort(key=lambda i: i["data_flow_score"], reverse=True)

    if items:
        max_score = items[0]["data_flow_score"]
        avg_score = round(sum(i["data_flow_score"] for i in items) / len(items), 2)
        overall = _calibrate(max_score)
        heavy = [i for i in items if i["data_flow_score"] > 20]
    else:
        max_score = avg_score = 0.0
        overall = "L1"
        heavy = []

    return {
        "complexity": "Data Flow Complexity",
        "sno": 12,
        "language": tree.get("language", "unknown"),
        "summary": {
            "level": overall,
            "score": max_score,
            "headline": (f"{len(heavy)} data-heavy unit(s); "
                         f"{len([d for d, c in refs_by_data.items() if c > 1])} shared data element(s)"),
        },
        "metrics": {
            "units": len(items),
            "distinct_data_elements": len(refs_by_data),
            "shared_data_elements": len([d for d, c in refs_by_data.items() if c > 1]),
            "max_data_flow_score": max_score,
            "avg_data_flow_score": avg_score,
            "per_module_score": {k: round(v, 1) for k, v in module_scores.items()},
        },
        "hotspots": heavy[:10],
        "items": items,
    }


if __name__ == "__main__":
    import json
    demo = {
        "language": "java",
        "units": [
            {"id": "svc.transform", "name": "transform", "owner_type": "Svc",
             "params": ["order", "ctx"], "references": ["total", "tax", "cache"],
             "cfg": {"node_type": "SEQUENCE", "children": [
                 {"node_type": "CALL", "children": []},
                 {"node_type": "CALL", "children": []}]}},
            {"id": "svc.read", "name": "read", "owner_type": "Svc",
             "params": [], "references": ["cache"],
             "cfg": {"node_type": "SEQUENCE", "children": []}},
        ],
    }
    print(json.dumps(analyze(demo), indent=2))
