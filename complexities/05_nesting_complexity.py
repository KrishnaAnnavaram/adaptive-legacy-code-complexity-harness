"""
Complexity #05 - Nesting Complexity
===================================

What is it?      How deeply control structures are stacked inside one another.
Why needed?      Nesting depth is the cheapest reliable predictor of reading
                 difficulty, and it maps directly to a fix: flatten it. Depth is
                 also what cyclomatic complexity is blindest to - twenty flat
                 branches and four branches nested four deep can score the same
                 v(G), and only one of them is genuinely hard to follow.
How it works?    Maximum and mean nesting depth per unit, plus the amount of
                 code sitting at excessive depth. Reports the deepest construct
                 so the finding points somewhere specific.
Input required   units[].cfg
Output artifact  Nesting Complexity Report (uniform envelope).
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import (  # noqa: E402
    NESTING_NODES, Spec, Tree, cli_main, insufficient, level_from, result, worst,
)

SPEC = Spec(
    id="nesting_complexity", sno=5, name="Nesting Complexity", tier="structural",
    requires=["units", "cfg"],
    summary="Maximum and mean control-structure depth; the cheapest readability signal.",
)

# COBOL and PL/SQL nest more deeply by convention - cursor loops wrapped in
# exception blocks wrapped in conditionals are ordinary, not pathological.
BANDS = {
    "cobol": (4, 7, 10, 13),
    "plsql": (3, 5, 7, 9),
    "rpgle": (4, 7, 10, 13),
}
DEFAULT_BANDS = (3, 5, 7, 9)

DEEP_THRESHOLD = 4


def analyze(tree_raw: Dict[str, Any]) -> Dict[str, Any]:
    tree = Tree(tree_raw)
    tree.require(SPEC)
    bands = BANDS.get(tree.language, DEFAULT_BANDS)

    items = []
    for unit in tree.units:
        cfg = unit.get("cfg") or {}
        depths = []
        deepest_node = None
        deepest = 0
        at_depth: Dict[int, int] = defaultdict(int)

        for node, depth in Tree.walk_depth(cfg):
            nt = node.get("node_type")
            if nt in NESTING_NODES:
                depths.append(depth)
                at_depth[depth] += 1
                if depth > deepest:
                    deepest = depth
                    deepest_node = {"node_type": nt, "line": node.get("line"),
                                    "depth": depth}

        # Depth is measured on the constructs themselves; a unit with none is
        # flat by definition, which is depth 0 rather than "unknown".
        mean_depth = round(sum(depths) / len(depths), 2) if depths else 0.0
        deep_constructs = sum(v for k, v in at_depth.items() if k >= DEEP_THRESHOLD)

        items.append({
            "unit": unit.get("id"),
            "name": unit.get("name", unit.get("id")),
            "owner_type": unit.get("owner_type"),
            "start_line": unit.get("start_line"),
            "max_nesting": deepest,
            "mean_nesting": mean_depth,
            "nesting_constructs": len(depths),
            "constructs_at_depth": {str(k): v for k, v in sorted(at_depth.items())},
            "constructs_beyond_threshold": deep_constructs,
            "deepest_construct": deepest_node,
            "flat": deepest == 0,
            "score": float(deepest),
            "level": level_from(deepest, bands),
        })

    if not items:
        insufficient("tree contains no units")

    scores = [i["score"] for i in items]
    deep_units = [i for i in items if i["max_nesting"] >= DEEP_THRESHOLD]
    flat_units = [i for i in items if i["flat"]]

    return result(
        SPEC, tree,
        level=worst(i["level"] for i in items),
        score=max(scores),
        headline=(f"{len(items)} unit(s); deepest nesting {int(max(scores))}; "
                  f"{len(deep_units)} unit(s) at depth >= {DEEP_THRESHOLD}; "
                  f"{len(flat_units)} flat"),
        metrics={
            "units": len(items),
            "max_nesting_observed": int(max(scores)),
            "avg_max_nesting": round(sum(scores) / len(items), 2),
            "units_beyond_threshold": len(deep_units),
            "flat_units": len(flat_units),
            "total_deep_constructs": sum(i["constructs_beyond_threshold"] for i in items),
            "deep_threshold": DEEP_THRESHOLD,
            "bands_applied": list(bands),
            "band_source": "language" if tree.language in BANDS else "default",
        },
        confidence=1.0,
        hotspots=sorted(deep_units, key=lambda i: -i["score"])[:10],
        items=items,
        extra={"remediation": (
            "Nesting is the most mechanically fixable form of complexity: guard "
            "clauses and early returns flatten it without changing behaviour. "
            "Address it before cyclomatic complexity - it is cheaper and it "
            "reduces cognitive complexity at the same time."
        )},
    )


if __name__ == "__main__":
    raise SystemExit(cli_main(analyze, SPEC))
