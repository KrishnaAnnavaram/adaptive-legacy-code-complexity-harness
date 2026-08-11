"""
Complexity #13 - Inheritance Complexity
=======================================

What is it?      The complexity added by inheritance hierarchies - how far up a
                 chain you must read to know what a type actually does.
Why needed?      Deep or wide inheritance scatters behaviour across ancestors.
                 To understand a leaf class you must hold its whole chain in your
                 head, and a change to a base class silently reaches every
                 descendant. It is a primary readability and change-risk driver in
                 OO estates, and a decomposition concern when a base type is a hub.
How it works?    Classic Chidamber & Kemerer hierarchy metrics per type:
                   DIT - Depth of Inheritance Tree (longest chain to a root)
                   NOC - Number of Children (direct subtypes)
                 plus interface count and multiple-inheritance flags.
Input required   types[]  with extends / implements
Output artifact  Inheritance Complexity Report (uniform envelope).

Theory: Chidamber & Kemerer 1994, "A Metrics Suite for Object Oriented Design".

LANGUAGE NEUTRALITY
    Applies wherever the parser recorded an `extends` relation - Java, C#, C++,
    Python, PL/SQL object types. Procedural languages with no inheritance simply
    produce DIT 0 for every type, which is a true measurement, not a gap.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import (  # noqa: E402
    Spec, Tree, cli_main, insufficient, level_from, result, worst,
)

SPEC = Spec(
    id="inheritance_complexity", sno=13, name="Inheritance Complexity", tier="coupling",
    requires=["types"], scope="type",
    summary="Depth (DIT) and width (NOC) of type hierarchies.",
)

# Classic guidance treats DIT > 5 as risky; bands: 1 / 2 / 4 / 6.
BANDS = (1, 2, 4, 6)


def _dit(type_id: str, parents: Dict[str, List[str]],
         memo: Dict[str, int], visiting: Set[str]) -> int:
    """Depth of inheritance tree: longest chain to a root. Cycle-safe."""
    if type_id in memo:
        return memo[type_id]
    if type_id in visiting:                 # illegal inheritance cycle - defend
        return 0
    visiting.add(type_id)
    ancestors = parents.get(type_id, [])
    depth = 0 if not ancestors else 1 + max(_dit(p, parents, memo, visiting)
                                            for p in ancestors)
    visiting.discard(type_id)
    memo[type_id] = depth
    return depth


def analyze(tree_raw: Dict[str, Any]) -> Dict[str, Any]:
    tree = Tree(tree_raw)
    tree.require(SPEC)

    types = tree.types
    by_id = {t.get("id"): t for t in types}

    parents: Dict[str, List[str]] = {}
    children: Dict[str, int] = {t.get("id"): 0 for t in types}
    for t in types:
        supers = [s for s in (t.get("extends") or []) if s in by_id]
        parents[t.get("id")] = supers
        for s in supers:
            children[s] = children.get(s, 0) + 1

    memo: Dict[str, int] = {}
    items: List[Dict[str, Any]] = []
    for t in types:
        tid = t.get("id")
        dit = _dit(tid, parents, memo, set())
        noc = children.get(tid, 0)
        n_super = len(parents.get(tid, []))
        items.append({
            "type_id": tid,
            "name": t.get("name", tid),
            "kind": t.get("kind", "class"),
            "dit": dit,
            "noc": noc,
            "interfaces_implemented": len(t.get("implements") or []),
            "superclasses": n_super,
            "multiple_inheritance": n_super > 1,
            "score": float(dit),
            "level": level_from(dit, BANDS),
        })

    if not items:
        insufficient("tree carries no types")

    items.sort(key=lambda i: (-i["dit"], -i["noc"], i["type_id"]))
    max_dit = max(i["dit"] for i in items)
    max_noc = max(i["noc"] for i in items)
    deep = [i for i in items if i["dit"] >= 4]

    return result(
        SPEC, tree,
        level=worst(i["level"] for i in items),
        score=float(max_dit),
        headline=(f"{len(items)} type(s); max inheritance depth {max_dit}; "
                  f"widest base has {max_noc} child(ren); {len(deep)} deep hierarchy(ies)"),
        metrics={
            "types": len(items),
            "max_dit": max_dit,
            "avg_dit": round(sum(i["dit"] for i in items) / len(items), 2),
            "max_noc": max_noc,
            "types_with_multiple_inheritance": sum(1 for i in items if i["multiple_inheritance"]),
            "deep_hierarchies": len(deep),
            "bands_applied": list(BANDS),
        },
        confidence=1.0,
        hotspots=deep[:10],
        items=items,
        extra={"interpretation": (
            "High DIT is a comprehension cost (read the whole chain to understand a "
            "leaf); high NOC is a change-risk cost (a base-class edit reaches every "
            "child). They are different problems and are reported separately."
        )},
    )


if __name__ == "__main__":
    raise SystemExit(cli_main(analyze, SPEC))
