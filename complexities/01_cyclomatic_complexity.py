"""
Complexity #01 - Cyclomatic Complexity  (McCabe v(G))
=====================================================

What is it?      The number of linearly independent paths through a unit.
Why needed?      It is the lower bound on how many test cases you need for full
                 branch coverage, and the most widely understood complexity
                 number in existence. Every estimate conversation starts here.
How it works?    v(G) = 1 + decision nodes. ELSE and DEFAULT deliberately add
                 nothing: the path already exists as the false arm of the branch
                 above them. Counting them inflates every unit by one per
                 branch, which is the most common way this metric is got wrong.
Input required   units[].cfg
Output artifact  Cyclomatic Complexity Report (uniform envelope).

Theory: McCabe 1976, "A Complexity Measure", IEEE TSE SE-2(4).
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import (  # noqa: E402
    DECISION_NODES, Spec, Tree, cli_main, level_from, result, worst,
)

SPEC = Spec(
    id="cyclomatic_complexity", sno=1, name="Cyclomatic Complexity", tier="structural",
    requires=["units", "cfg"], optional=["loc"],
    summary="Independent paths per unit; the floor on branch-coverage test cases.",
)

# Bands are language-calibrated. COBOL paragraphs and RPG calculation specs
# routinely carry branch counts that would be alarming in a 3GL method, so a
# threshold of 10 flags every production paragraph and discriminates nothing.
BANDS = {
    "cobol":  (15, 35, 55, 75),
    "rpgle":  (15, 30, 45, 60),
    "pli":    (15, 30, 45, 60),
    "plsql":  (10, 20, 30, 40),
    "natural": (12, 25, 40, 55),
}
DEFAULT_BANDS = (10, 20, 35, 50)


def analyze(tree_raw: Dict[str, Any]) -> Dict[str, Any]:
    tree = Tree(tree_raw)
    degraded = tree.require(SPEC)
    bands = BANDS.get(tree.language, DEFAULT_BANDS)

    items = []
    for unit in tree.units:
        cfg = unit.get("cfg") or {}
        by_kind: Dict[str, int] = {}
        for node in Tree.walk(cfg):
            nt = node.get("node_type")
            if nt in DECISION_NODES:
                by_kind[nt] = by_kind.get(nt, 0) + 1

        decisions = sum(by_kind.values())
        vg = 1 + decisions
        dominant = max(by_kind.items(), key=lambda kv: kv[1]) if by_kind else None

        items.append({
            "unit": unit.get("id"),
            "name": unit.get("name", unit.get("id")),
            "owner_type": unit.get("owner_type"),
            "start_line": unit.get("start_line"),
            "cyclomatic": vg,
            "decision_points": decisions,
            "decisions_by_kind": dict(sorted(by_kind.items())),
            "dominant_construct": dominant[0] if dominant else None,
            "min_test_cases": vg,
            "score": float(vg),
            "level": level_from(vg, bands),
        })

    if not items:
        from _core import insufficient
        insufficient("tree contains no units")

    scores = [i["score"] for i in items]
    total = int(sum(scores))
    max_vg = max(scores)
    hot = sorted([i for i in items if i["level"] in ("L4", "L5")],
                 key=lambda i: -i["score"])

    return result(
        SPEC, tree,
        level=worst(i["level"] for i in items),
        score=max_vg,
        headline=(f"{len(items)} unit(s); max v(G) {int(max_vg)}; "
                  f"{total} test case(s) needed for branch coverage; "
                  f"{len(hot)} unit(s) above threshold"),
        metrics={
            "units": len(items),
            "total_cyclomatic": total,
            "max_cyclomatic": int(max_vg),
            "avg_cyclomatic": round(total / len(items), 2),
            "min_test_cases_total": total,
            "units_above_threshold": len(hot),
            "bands_applied": list(bands),
            "band_source": "language" if tree.language in BANDS else "default",
        },
        confidence=1.0 if not degraded else 0.9,
        confidence_reasons=[f"optional input '{f}' absent" for f in degraded],
        hotspots=hot[:10],
        items=items,
    )


if __name__ == "__main__":
    raise SystemExit(cli_main(analyze, SPEC))
