"""
Complexity #07 - Structural Complexity
======================================

What is it?      The shape and size of the codebase: how much there is, how it
                 is distributed, and whether that distribution is healthy.
Why needed?      Every other metric reports a per-unit score. This one reports
                 the SHAPE of the estate, which is what drives planning. Ten
                 thousand lines spread evenly over 200 units is a very different
                 job from the same ten thousand lines with 80% in three units -
                 and the average complexity is identical in both cases.
How it works?    Size and statement counts per unit, then distribution measures
                 over the whole tree: concentration (what share of the code sits
                 in the largest units), spread, and the count of outliers that
                 dominate the estate.
Input required   units[]
Output artifact  Structural Complexity Report (uniform envelope).

WHY CONCENTRATION MATTERS
    A mean hides the two 3,000-line paragraphs that are the actual migration
    risk. Concentration is reported explicitly so the plan is built around the
    outliers rather than the average.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import (  # noqa: E402
    DECISION_NODES, Spec, Tree, cli_main, insufficient, level_from, result,
)

SPEC = Spec(
    id="structural_complexity", sno=7, name="Structural Complexity", tier="size",
    requires=["units"], optional=["cfg", "loc", "comment_lines"],
    scope="tree",
    summary="Size and its distribution across the estate; where the mass actually sits.",
)

BANDS = (0.25, 0.40, 0.60, 0.80)   # concentration of code in the top 10% of units


def _percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return float(s[lo] + (s[hi] - s[lo]) * (pos - lo))


def analyze(tree_raw: Dict[str, Any]) -> Dict[str, Any]:
    tree = Tree(tree_raw)
    degraded = tree.require(SPEC)

    items = []
    for unit in tree.units:
        cfg = unit.get("cfg") or {}
        loc = int(unit.get("loc", 0) or 0)
        if not loc and unit.get("start_line") and unit.get("end_line"):
            loc = unit["end_line"] - unit["start_line"] + 1

        nodes = sum(1 for _ in Tree.walk(cfg)) if cfg else 0
        decisions = Tree.count(cfg, DECISION_NODES) if cfg else 0
        comments = int(unit.get("comment_lines", 0) or 0)

        items.append({
            "unit": unit.get("id"),
            "name": unit.get("name", unit.get("id")),
            "owner_type": unit.get("owner_type"),
            "start_line": unit.get("start_line"),
            "loc": loc,
            "cfg_nodes": nodes,
            "decision_points": decisions,
            "comment_lines": comments,
            "comment_ratio": round(comments / loc, 3) if loc else None,
            "decision_density": round(decisions / loc * 100, 2) if loc else None,
        })

    if not items:
        insufficient("tree contains no units")

    sizes = [i["loc"] for i in items]
    total_loc = sum(sizes)
    have_size = total_loc > 0

    if have_size:
        ranked = sorted(items, key=lambda i: -i["loc"])
        top_n = max(1, len(items) // 10)
        top_share = sum(i["loc"] for i in ranked[:top_n]) / total_loc
        median = _percentile([float(s) for s in sizes], 0.5)
        p90 = _percentile([float(s) for s in sizes], 0.90)
        # An outlier here means "dominates the estate", not "above average".
        outliers = [i for i in items if i["loc"] > max(p90, median * 3)]
    else:
        ranked, top_n, top_share, median, p90, outliers = items, 0, 0.0, 0.0, 0.0, []

    modules: Dict[str, int] = {}
    for i in items:
        modules[i["owner_type"] or "UNASSIGNED"] = \
            modules.get(i["owner_type"] or "UNASSIGNED", 0) + i["loc"]

    confidence = 1.0
    reasons = []
    if not have_size:
        confidence = 0.5
        reasons.append(
            "no loc or line ranges on any unit - size distribution is unmeasured "
            "and concentration is reported as 0, which is a MISSING value, not a "
            "flat distribution")
    if degraded:
        confidence = min(confidence, 0.85)
        reasons += [f"optional input '{f}' absent" for f in degraded]

    return result(
        SPEC, tree,
        level=level_from(top_share, BANDS) if have_size else "L1",
        score=round(top_share, 3),
        headline=(
            f"{len(items)} unit(s), {total_loc:,} line(s); "
            f"top {top_n} unit(s) hold {round(top_share * 100)}% of the code; "
            f"{len(outliers)} outlier(s)"
            if have_size else
            f"{len(items)} unit(s); SIZE NOT AVAILABLE - distribution unmeasured"
        ),
        metrics={
            "units": len(items),
            "modules": len(modules),
            "total_loc": total_loc,
            "mean_loc": round(total_loc / len(items), 1) if have_size else None,
            "median_loc": round(median, 1) if have_size else None,
            "p90_loc": round(p90, 1) if have_size else None,
            "max_loc": max(sizes) if have_size else None,
            "concentration_top_decile": round(top_share, 3) if have_size else None,
            "outlier_units": len(outliers),
            "total_cfg_nodes": sum(i["cfg_nodes"] for i in items),
            "total_decision_points": sum(i["decision_points"] for i in items),
            "avg_decision_density": round(
                sum(i["decision_density"] or 0 for i in items) / len(items), 2),
            "loc_by_module": dict(sorted(modules.items(), key=lambda kv: -kv[1])[:20]),
            "bands_applied": list(BANDS),
        },
        confidence=confidence,
        confidence_reasons=reasons,
        hotspots=ranked[:10] if have_size else [],
        items=items,
        extra={"interpretation": (
            "concentration_top_decile is the share of all code held by the largest "
            "10% of units. Above 0.60 the estate is effectively a handful of large "
            "units plus noise, and planning should be built around those units "
            "individually rather than around an average."
        )},
    )


if __name__ == "__main__":
    raise SystemExit(cli_main(analyze, SPEC))
