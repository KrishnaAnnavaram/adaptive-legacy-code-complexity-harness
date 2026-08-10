"""
Complexity #03 - Control Flow Complexity
========================================

What is it?      How STRUCTURED the flow is - whether it reduces to clean
                 nested blocks, or contains jumps that make it irreducible.
Why needed?      This is the metric that decides whether automated translation
                 is even possible. Cyclomatic complexity tells you how many
                 tests you need; this tells you whether the unit can be
                 mechanically restructured at all. For COBOL, RPG and PL/I it
                 is the single highest-value structural number, well above v(G).
How it works?    Approximates McCabe's essential complexity. Well-structured
                 constructs (if/else, loops, case) reduce away and cost nothing.
                 What remains after reduction is what makes flow irreducible:
                 GOTO, ALTER, PERFORM THRU ranges, paragraph fall-through and
                 multiple exit points.
Input required   units[].cfg
Output artifact  Control Flow Complexity Report (uniform envelope).

Theory: McCabe 1976 (essential complexity, ev(G)).

HONESTY NOTE
    True ev(G) requires collapsing a real control-flow GRAPH. A tree of CFG
    nodes is not a graph - it has no edges. What is computed here is therefore
    an UNSTRUCTUREDNESS INDEX derived from the jump constructs present, and it
    is reported under that name. It is a sound proxy and a deliberately
    conservative one, but it is not ev(G) and is not labelled as such.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import (  # noqa: E402
    JUMP_NODES, Spec, Tree, cli_main, insufficient, level_from, result, worst,
)

SPEC = Spec(
    id="control_flow_complexity", sno=3, name="Control Flow Complexity", tier="structural",
    requires=["units", "cfg"],
    summary="Unstructuredness of flow; decides whether mechanical translation is viable.",
)

BANDS = (0, 3, 8, 16)

# Cost of each irreducible construct. ALTER dominates because it rewrites a
# jump target at RUNTIME - in its presence no statically-derived control-flow
# graph is correct, which invalidates every other structural metric for that unit.
_JUMP_COST = {
    "ALTER": 12.0,
    "GOTO": 3.0,
    "PERFORM_THRU": 4.0,
    "FALL_THROUGH": 2.5,
}

_EXIT_NODES = {"RETURN", "EXIT"}


def analyze(tree_raw: Dict[str, Any]) -> Dict[str, Any]:
    tree = Tree(tree_raw)
    tree.require(SPEC)

    items = []
    for unit in tree.units:
        cfg = unit.get("cfg") or {}
        jumps: Dict[str, int] = {}
        exits = 0
        deep_jumps = 0

        for node, depth in Tree.walk_depth(cfg):
            nt = node.get("node_type")
            if nt in JUMP_NODES:
                jumps[nt] = jumps.get(nt, 0) + 1
                if depth >= 2:
                    deep_jumps += 1
            elif nt in _EXIT_NODES:
                exits += 1

        score = sum(_JUMP_COST.get(k, 2.0) * v for k, v in jumps.items())
        # A jump from inside nested structure is worse than one at the top: it
        # crosses block boundaries, which is precisely what prevents reduction.
        score += deep_jumps * 2.0
        # Multiple exits are not a defect on their own; several are a smell.
        if exits > 2:
            score += (exits - 2) * 1.0

        structured = not jumps
        reasons = []
        if "ALTER" in jumps:
            reasons.append(
                f"{jumps['ALTER']} ALTER statement(s) - jump target is rewritten at "
                f"runtime; no static control-flow analysis of this unit is reliable")
        if "GOTO" in jumps:
            reasons.append(f"{jumps['GOTO']} GOTO(s)")
        if "PERFORM_THRU" in jumps:
            reasons.append(
                f"{jumps['PERFORM_THRU']} PERFORM THRU range(s) - behaviour depends on "
                f"paragraph ORDER, so reordering during conversion changes semantics")
        if "FALL_THROUGH" in jumps:
            reasons.append(f"{jumps['FALL_THROUGH']} fall-through path(s)")
        if deep_jumps:
            reasons.append(f"{deep_jumps} jump(s) from nesting depth >= 2")
        if exits > 2:
            reasons.append(f"{exits} exit points")

        items.append({
            "unit": unit.get("id"),
            "name": unit.get("name", unit.get("id")),
            "owner_type": unit.get("owner_type"),
            "start_line": unit.get("start_line"),
            "unstructuredness_index": round(score, 1),
            "structured": structured,
            "jumps_by_kind": dict(sorted(jumps.items())),
            "total_jumps": sum(jumps.values()),
            "jumps_from_nesting": deep_jumps,
            "exit_points": exits,
            "mechanically_translatable": score < 8,
            "score": round(score, 1),
            "level": level_from(score, BANDS),
            "reasons": reasons,
        })

    if not items:
        insufficient("tree contains no units")

    scores = [i["score"] for i in items]
    structured_units = [i for i in items if i["structured"]]
    blocked = [i for i in items if not i["mechanically_translatable"]]
    has_alter = [i for i in items if "ALTER" in i["jumps_by_kind"]]

    return result(
        SPEC, tree,
        level=worst(i["level"] for i in items),
        score=max(scores),
        headline=(f"{len(structured_units)}/{len(items)} unit(s) fully structured; "
                  f"{len(blocked)} not mechanically translatable; "
                  f"{len(has_alter)} contain ALTER"),
        metrics={
            "units": len(items),
            "fully_structured_units": len(structured_units),
            "structured_ratio": round(len(structured_units) / len(items), 3),
            "units_blocking_translation": len(blocked),
            "total_jumps": sum(i["total_jumps"] for i in items),
            "units_with_alter": len(has_alter),
            "max_unstructuredness": max(scores),
            "avg_unstructuredness": round(sum(scores) / len(items), 2),
            "bands_applied": list(BANDS),
        },
        confidence=0.8,
        confidence_reasons=[
            "computed as an unstructuredness index from jump constructs, not as "
            "true McCabe ev(G) - a CFG node tree carries no edges to reduce"
        ],
        hotspots=sorted(blocked, key=lambda i: -i["score"])[:10],
        items=items,
        extra={"note": (
            "Units with mechanically_translatable=false must be restructured by hand "
            "before any automated conversion. This is the metric that scopes that work."
        )},
    )


if __name__ == "__main__":
    raise SystemExit(cli_main(analyze, SPEC))
