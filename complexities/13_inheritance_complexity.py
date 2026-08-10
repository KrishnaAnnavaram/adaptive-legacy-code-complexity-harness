"""
Complexity #13 - Inheritance Complexity
=======================================

What is it?      Complexity introduced by inheritance hierarchies.
Why needed?      Deep or wide inheritance makes behavior hard to trace (you must
                 follow the chain to know what a class actually does).
How it works?    From the class hierarchy it computes classic OO metrics:
                   * DIT  - Depth of Inheritance Tree (how far up the chain)
                   * NOC  - Number of Children (how many classes extend it)
                   * multiple-inheritance / interface fan-in
                 then derives an L1-L5 level.
Input required   Class hierarchy / AST (types with extends / implements).
Output artifact  Inheritance Complexity Report (returned as a dict).

--------------------------------------------------------------------------------
INPUT CONTRACT (subset of the Normalized Tree used here)
--------------------------------------------------------------------------------
tree = {
  "language": "java",
  "types": [ {
      "id","name","kind",                # kind: class|interface|abstract
      "extends":    [type_id, ...],      # superclasses
      "implements": [type_id, ...],      # implemented interfaces
      "methods":    [unit_id, ...]       # optional; for override signal
  }, ... ]
}
"""

from __future__ import annotations
from typing import Any, Dict, List, Set

# Calibration on Depth of Inheritance Tree (DIT). Classic guidance: DIT>5 is risky.
_DIT_BANDS = [(1, "L1"), (2, "L2"), (4, "L3"), (6, "L4")]  # else L5


def _calibrate(dit: int) -> str:
    for threshold, level in _DIT_BANDS:
        if dit <= threshold:
            return level
    return "L5"


def _dit(type_id: str, parents: Dict[str, List[str]], memo: Dict[str, int],
         visiting: Set[str]) -> int:
    """Depth of inheritance tree: longest chain up to a root. Cycle-safe."""
    if type_id in memo:
        return memo[type_id]
    if type_id in visiting:      # inheritance cycle (illegal, but defend anyway)
        return 0
    visiting.add(type_id)
    ancestors = parents.get(type_id, [])
    depth = 0 if not ancestors else 1 + max(
        _dit(p, parents, memo, visiting) for p in ancestors
    )
    visiting.discard(type_id)
    memo[type_id] = depth
    return depth


def analyze(tree: Dict[str, Any]) -> Dict[str, Any]:
    types = tree.get("types", [])
    by_id = {t["id"]: t for t in types}

    # parents[c] = superclasses (extends only counts toward DIT; interfaces tracked separately)
    parents: Dict[str, List[str]] = {}
    children: Dict[str, int] = {t["id"]: 0 for t in types}
    for t in types:
        supers = [s for s in t.get("extends", []) if s in by_id]
        parents[t["id"]] = supers
        for s in supers:
            children[s] = children.get(s, 0) + 1

    memo: Dict[str, int] = {}
    items: List[Dict[str, Any]] = []
    for t in types:
        tid = t["id"]
        dit = _dit(tid, parents, memo, set())
        noc = children.get(tid, 0)
        impls = [i for i in t.get("implements", []) if i in by_id or True]
        multi = len(parents.get(tid, []))
        items.append({
            "type_id": tid,
            "name": t.get("name", tid),
            "kind": t.get("kind", "class"),
            "dit": dit,
            "noc": noc,
            "interfaces_implemented": len(impls),
            "superclasses": multi,
            "multiple_inheritance": multi > 1,
            "level": _calibrate(dit),
        })

    items.sort(key=lambda i: (i["dit"], i["noc"]), reverse=True)

    if items:
        max_dit = max(i["dit"] for i in items)
        avg_dit = round(sum(i["dit"] for i in items) / len(items), 2)
        max_noc = max(i["noc"] for i in items)
        overall = _calibrate(max_dit)
        deep = [i for i in items if i["dit"] >= 4]
    else:
        max_dit = avg_dit = max_noc = 0
        overall = "L1"
        deep = []

    return {
        "complexity": "Inheritance Complexity",
        "sno": 13,
        "language": tree.get("language", "unknown"),
        "summary": {
            "level": overall,
            "score": max_dit,
            "headline": (f"Max inheritance depth {max_dit}, widest class has {max_noc} "
                         f"child class(es); {len(deep)} deep hierarchy(ies)"),
        },
        "metrics": {
            "types": len(items),
            "max_dit": max_dit,
            "avg_dit": avg_dit,
            "max_noc": max_noc,
            "classes_with_multiple_inheritance": sum(1 for i in items if i["multiple_inheritance"]),
            "deep_hierarchies": len(deep),
        },
        "hotspots": deep[:10],
        "items": items,
    }


if __name__ == "__main__":
    import json
    demo = {
        "language": "java",
        "types": [
            {"id": "Base", "name": "Base", "kind": "class", "extends": []},
            {"id": "Mid", "name": "Mid", "kind": "class", "extends": ["Base"]},
            {"id": "Leaf", "name": "Leaf", "kind": "class", "extends": ["Mid"],
             "implements": ["Comparable"]},
            {"id": "Leaf2", "name": "Leaf2", "kind": "class", "extends": ["Mid"]},
        ],
    }
    print(json.dumps(analyze(demo), indent=2))
