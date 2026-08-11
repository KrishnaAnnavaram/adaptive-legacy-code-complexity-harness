"""
Complexity #02 - Cognitive Complexity
=====================================

What is it?      How hard a unit is for a human to READ and hold in their head.
Why needed?      Cyclomatic complexity counts paths, which is what a test suite
                 cares about. It does not care where those paths sit. A flat
                 switch with 20 arms and a 4-deep nest of ifs can score the same
                 v(G), yet one is skimmable and the other is not. Cognitive
                 complexity is the metric that separates them, and it is the one
                 that correlates with how long a change actually takes.
How it works?    Three rules, after Campbell/SonarSource:
                   1. +1 for each break in the linear flow (if, loop, catch, jump)
                   2. +N extra where N is the current nesting depth
                   3. no increment for structures that do not break flow (else,
                      and shorthand chains), because reading them costs nothing
                      extra once the branch above is understood
Input required   units[].cfg
Output artifact  Cognitive Complexity Report (uniform envelope).

Theory: G. Ann Campbell, "Cognitive Complexity - A new way of measuring
understandability", SonarSource 2018.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import (  # noqa: E402
    BRANCH_NODES, JUMP_NODES, LOOP_NODES, Spec, Tree, cli_main, insufficient,
    level_from, result, worst,
)

SPEC = Spec(
    id="cognitive_complexity", sno=2, name="Cognitive Complexity", tier="structural",
    requires=["units", "cfg"], optional=["loc"],
    summary="Readability cost; penalises nesting, unlike cyclomatic complexity.",
)

BANDS = (5, 15, 25, 40)

# Boolean operators increment once for a whole sequence, not per operator, and
# they take no nesting bonus - `a && b && c` is one thing to understand.
_FLAT_INCREMENT = {"AND", "OR", "TERNARY"}
_NESTED_INCREMENT = (BRANCH_NODES - _FLAT_INCREMENT) | LOOP_NODES


def analyze(tree_raw: Dict[str, Any]) -> Dict[str, Any]:
    tree = Tree(tree_raw)
    degraded = tree.require(SPEC)

    items = []
    for unit in tree.units:
        cfg = unit.get("cfg") or {}
        score = 0
        nesting_penalty = 0
        breaks = 0
        deepest = 0

        for node, depth in Tree.walk_depth(cfg):
            nt = node.get("node_type")
            deepest = max(deepest, depth)
            if nt in _NESTED_INCREMENT:
                # Rule 1 + Rule 2: base increment plus the depth it sits at.
                score += 1 + depth
                nesting_penalty += depth
                breaks += 1
            elif nt in _FLAT_INCREMENT:
                score += 1
                breaks += 1
            elif nt in JUMP_NODES:
                # A jump forces the reader to leave the current context entirely.
                score += 1 + depth
                nesting_penalty += depth
                breaks += 1

        cyclomatic = Tree.cyclomatic(cfg)
        # The gap between the two metrics IS the finding: a large gap means the
        # difficulty is structural (nesting), not merely a lot of branches.
        gap = score - cyclomatic

        items.append({
            "unit": unit.get("id"),
            "name": unit.get("name", unit.get("id")),
            "owner_type": unit.get("owner_type"),
            "start_line": unit.get("start_line"),
            "cognitive": score,
            "cyclomatic": cyclomatic,
            "nesting_penalty": nesting_penalty,
            "flow_breaks": breaks,
            "max_nesting": deepest,
            "gap_vs_cyclomatic": gap,
            "difficulty_driver": (
                "nesting" if nesting_penalty > breaks else
                "branch_count" if breaks else "none"
            ),
            "score": float(score),
            "level": level_from(score, BANDS),
        })

    if not items:
        insufficient("tree contains no units")

    scores = [i["score"] for i in items]
    max_score = max(scores)
    nesting_driven = [i for i in items if i["difficulty_driver"] == "nesting"]
    hot = sorted([i for i in items if i["level"] in ("L4", "L5")],
                 key=lambda i: -i["score"])

    return result(
        SPEC, tree,
        level=worst(i["level"] for i in items),
        score=max_score,
        headline=(f"{len(items)} unit(s); max cognitive {int(max_score)}; "
                  f"{len(nesting_driven)} unit(s) hard because of NESTING rather "
                  f"than branch count"),
        metrics={
            "units": len(items),
            "total_cognitive": int(sum(scores)),
            "max_cognitive": int(max_score),
            "avg_cognitive": round(sum(scores) / len(items), 2),
            "total_nesting_penalty": sum(i["nesting_penalty"] for i in items),
            "nesting_driven_units": len(nesting_driven),
            "max_gap_vs_cyclomatic": max(i["gap_vs_cyclomatic"] for i in items),
            "bands_applied": list(BANDS),
        },
        confidence=1.0 if not degraded else 0.9,
        confidence_reasons=[f"optional input '{f}' absent" for f in degraded],
        hotspots=hot[:10],
        items=items,
        extra={"interpretation": (
            "A large gap_vs_cyclomatic means the unit is hard to READ rather than "
            "hard to TEST. Flattening the nesting fixes it; splitting out branches "
            "does not."
        )},
    )


if __name__ == "__main__":
    raise SystemExit(cli_main(analyze, SPEC))
