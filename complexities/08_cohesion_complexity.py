"""
Complexity #8 - Cohesion Complexity
===================================

What is it?      Measures how closely related the responsibilities inside a
                 class / module are.
Why needed?      Low cohesion signals mixed responsibilities and hard-to-maintain
                 code (a class doing too many unrelated things).
How it works?    For every type (class/module) it measures how much the methods
                 share the same fields / state.  Uses the LCOM family of metrics.
Input required   Class/module structure + data references  -> the Normalized Tree.
Output artifact  Cohesion Complexity Report (returned as a dict).

--------------------------------------------------------------------------------
INPUT CONTRACT (the parser's Normalized Tree = AST + call graph + dependency graph)
--------------------------------------------------------------------------------
tree = {
  "language": "java",
  "units": [ { "id","name","owner_type", "references": [field_id, ...] }, ... ],
  "types": [ { "id","name","kind","fields":[field_id,...], "methods":[unit_id,...] }, ... ],
  "call_graph": { "nodes":[unit_id,...], "edges":[{"from":unit_id,"to":unit_id}, ...] },
}
Only the fields above are used by this analyzer; anything else is ignored.
"""

from __future__ import annotations
from itertools import combinations
from typing import Any, Dict, List


# ----------------------------------------------------------------------------- #
# L1-L5 calibration
# ----------------------------------------------------------------------------- #
# LCOM4 == number of connected components of methods within a class.
# 1 => perfectly cohesive; the higher the value the more the class should be split.
_LCOM4_BANDS = [(1, "L1"), (2, "L2"), (3, "L3"), (5, "L4")]  # else L5


def _calibrate(lcom4: int) -> str:
    for threshold, level in _LCOM4_BANDS:
        if lcom4 <= threshold:
            return level
    return "L5"


# ----------------------------------------------------------------------------- #
# Union-Find (for LCOM4 connected components)
# ----------------------------------------------------------------------------- #
class _DSU:
    def __init__(self, items: List[str]) -> None:
        self.parent = {i: i for i in items}

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb

    def components(self) -> int:
        return len({self.find(x) for x in self.parent})


# ----------------------------------------------------------------------------- #
# Core analysis
# ----------------------------------------------------------------------------- #
def _analyze_type(t: Dict[str, Any],
                  unit_refs: Dict[str, set],
                  call_pairs: set) -> Dict[str, Any]:
    method_ids = [m for m in t.get("methods", []) if m in unit_refs]
    fields = set(t.get("fields", []))
    n = len(method_ids)

    if n <= 1:
        # A class with 0 or 1 method is trivially cohesive.
        return {
            "type_id": t["id"], "name": t.get("name", t["id"]),
            "methods": n, "fields": len(fields),
            "lcom4": 1, "lcom_hs": 0.0, "shared_pairs": 0, "total_pairs": 0,
            "level": "L1",
        }

    # --- LCOM4: connect two methods that share a field OR call each other ----- #
    dsu = _DSU(method_ids)
    shared_pairs = 0
    total_pairs = 0
    for a, b in combinations(method_ids, 2):
        total_pairs += 1
        shares_field = bool(unit_refs[a] & unit_refs[b] & fields)
        linked_by_call = (a, b) in call_pairs or (b, a) in call_pairs
        if shares_field or linked_by_call:
            dsu.union(a, b)
            if shares_field:
                shared_pairs += 1
    lcom4 = dsu.components()

    # --- LCOM (Henderson-Sellers): 0 = cohesive, ~1 = no cohesion ------------ #
    if fields:
        accesses = sum(len(unit_refs[m] & fields) for m in method_ids)
        mean_access = accesses / len(fields)          # avg methods touching a field
        denom = (1 - n) if n != 1 else 1
        lcom_hs = (mean_access - n) / denom if denom else 0.0
        lcom_hs = max(0.0, min(1.0, lcom_hs))
    else:
        lcom_hs = 1.0  # methods but no shared state at all

    return {
        "type_id": t["id"], "name": t.get("name", t["id"]),
        "methods": n, "fields": len(fields),
        "lcom4": lcom4,
        "lcom_hs": round(lcom_hs, 3),
        "shared_pairs": shared_pairs,
        "total_pairs": total_pairs,
        "level": _calibrate(lcom4),
    }


def analyze(tree: Dict[str, Any]) -> Dict[str, Any]:
    """Compute cohesion complexity for every type in the normalized tree."""
    unit_refs = {u["id"]: set(u.get("references", []) or [])
                 for u in tree.get("units", [])}

    call_pairs = {(e["from"], e["to"])
                  for e in tree.get("call_graph", {}).get("edges", [])}

    items = [_analyze_type(t, unit_refs, call_pairs) for t in tree.get("types", [])]

    if items:
        worst_lcom4 = max(i["lcom4"] for i in items)
        avg_lcom4 = round(sum(i["lcom4"] for i in items) / len(items), 2)
        avg_lcom_hs = round(sum(i["lcom_hs"] for i in items) / len(items), 3)
        overall = _calibrate(worst_lcom4)
        low_cohesion = [i for i in items if i["lcom4"] >= 3]
    else:
        worst_lcom4 = avg_lcom4 = 0
        avg_lcom_hs = 0.0
        overall = "L1"
        low_cohesion = []

    return {
        "complexity": "Cohesion Complexity",
        "sno": 8,
        "language": tree.get("language", "unknown"),
        "summary": {
            "level": overall,
            "score": worst_lcom4,
            "headline": f"{len(low_cohesion)} type(s) show low cohesion (LCOM4>=3)",
        },
        "metrics": {
            "types_analyzed": len(items),
            "worst_lcom4": worst_lcom4,
            "avg_lcom4": avg_lcom4,
            "avg_lcom_hs": avg_lcom_hs,
        },
        "hotspots": sorted(low_cohesion, key=lambda i: i["lcom4"], reverse=True),
        "items": items,
    }


# ----------------------------------------------------------------------------- #
# Standalone demo
# ----------------------------------------------------------------------------- #

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
    id='cohesion_complexity',
    sno=8,
    name='Cohesion Complexity',
    tier='coupling',
    requires=['units', 'types'],
    optional=['call_graph', 'references'],
    summary='How well the members of a type belong together.'
)

if __name__ == "__main__":
    raise SystemExit(_cli_main(analyze, SPEC))
