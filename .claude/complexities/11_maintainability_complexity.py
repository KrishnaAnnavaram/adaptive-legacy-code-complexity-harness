"""
Complexity #11 - Maintainability Complexity  (DERIVED)
======================================================

What is it?      The overall difficulty of maintaining a unit over time, on the
                 standard 0-100 Maintainability Index scale.
Why needed?      It is the single number stakeholders ask for, and the one an AI
                 must NOT invent. Its value is that it is DERIVED transparently
                 from measurable inputs - size, branching, volume, comments - so
                 every point traces to something real rather than to a judgement.
How it works?    Maintainability Index (SEI/Microsoft variant):
                     MI = MAX(0, 171 - 5.2*ln(V) - 0.23*CC - 16.2*ln(LOC)) * 100/171
                 plus a bounded comment-density bonus. V = Halstead volume,
                 CC = cyclomatic complexity (shared with #01 via Tree.cyclomatic
                 so the two never disagree), LOC = lines of code. Higher MI is
                 easier to maintain, so the level scale is inverted.
Input required   units[].cfg, units[].loc  (halstead, comment_lines refine it)
Output artifact  Maintainability Report (uniform envelope).

Theory: Oman & Hagemeister 1992; SEI Maintainability Index.

LANGUAGE NEUTRALITY
    Every input is language-neutral: a line count, a decision count from the CFG,
    an optional Halstead volume. Bands are the same everywhere because the MI
    scale is already normalized to 0-100.
"""

from __future__ import annotations

import math
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import (  # noqa: E402
    Spec, Tree, cli_main, insufficient, level_from_inverted, result, worst,
)

SPEC = Spec(
    id="maintainability_complexity", sno=11, name="Maintainability Complexity",
    tier="composite", requires=["units", "cfg", "loc"],
    optional=["halstead", "comment_lines"], depends_on=[1, 7],
    direction="lower_is_worse",
    summary="Maintainability Index derived from size, branching, volume and comments.",
)

# MI is higher-is-better, so these thresholds are DESCENDING and read with
# level_from_inverted: MI>=85 -> L1 (easy) ... MI<30 -> L5 (severe).
BANDS = (85, 70, 50, 30)


def _halstead_volume(unit: Dict[str, Any], cc: int, loc: int) -> float:
    """Use the parser's Halstead volume if present, else estimate from size."""
    vol = (unit.get("halstead") or {}).get("volume")
    if vol and vol > 0:
        return float(vol)
    approx = max(1.0, loc) * (3.0 + 0.5 * cc)
    return approx * math.log2(max(2.0, approx))


def _mi(loc: int, cc: int, volume: float, comment_ratio: float) -> float:
    loc = max(1, loc)
    volume = max(1.0, volume)
    raw = 171 - 5.2 * math.log(volume) - 0.23 * cc - 16.2 * math.log(loc)
    mi = max(0.0, raw) * 100.0 / 171.0
    mi += 50.0 * math.sin(math.sqrt(2.4 * comment_ratio))     # SEI comment bonus
    return max(0.0, min(100.0, mi))


def analyze(tree_raw: Dict[str, Any]) -> Dict[str, Any]:
    tree = Tree(tree_raw)
    degraded = tree.require(SPEC)

    items: List[Dict[str, Any]] = []
    for unit in tree.units:
        loc = int(unit.get("loc", 0) or 0)
        if not loc and unit.get("start_line") and unit.get("end_line"):
            loc = unit["end_line"] - unit["start_line"] + 1
        cc = Tree.cyclomatic(unit.get("cfg") or {})       # shared with #01
        volume = _halstead_volume(unit, cc, loc)
        comment_lines = int(unit.get("comment_lines", 0) or 0)
        comment_ratio = comment_lines / loc if loc else 0.0
        mi = _mi(loc, cc, volume, comment_ratio)
        items.append({
            "unit": unit.get("id"),
            "name": unit.get("name", unit.get("id")),
            "owner_type": unit.get("owner_type"),
            "loc": loc,
            "cyclomatic": cc,
            "halstead_volume": round(volume, 1),
            "comment_ratio": round(comment_ratio, 3),
            "maintainability_index": round(mi, 1),
            "score": round(mi, 1),
            "level": level_from_inverted(mi, BANDS),
        })

    if not items:
        insufficient("tree contains no units")

    weight = sum(max(1, i["loc"]) for i in items)
    weighted_mi = sum(i["maintainability_index"] * max(1, i["loc"]) for i in items) / weight
    worst_unit = min(items, key=lambda i: i["maintainability_index"])
    hard = [i for i in items if i["maintainability_index"] < 50]

    return result(
        SPEC, tree,
        level=worst(i["level"] for i in items),
        score=round(weighted_mi, 1),
        headline=(f"{len(items)} unit(s); LOC-weighted Maintainability Index "
                  f"{round(weighted_mi, 1)}/100; {len(hard)} hard-to-maintain unit(s)"),
        metrics={
            "units": len(items),
            "total_loc": sum(i["loc"] for i in items),
            "weighted_maintainability_index": round(weighted_mi, 1),
            "worst_unit": worst_unit["unit"],
            "worst_index": worst_unit["maintainability_index"],
            "hard_to_maintain_units": len(hard),
            "bands_applied": list(BANDS),
        },
        confidence=1.0 if not degraded else round(max(0.7, 1.0 - 0.15 * len(degraded)), 2),
        confidence_reasons=(
            [f"optional input '{f}' absent - "
             + ("Halstead volume estimated from size and branching" if f == "halstead"
                else "comment bonus omitted")
             for f in degraded]),
        hotspots=sorted(hard, key=lambda i: i["maintainability_index"])[:10],
        items=items,
        extra={"derived_from": ["LOC", "Cyclomatic Complexity", "Halstead Volume",
                                "Comment Density"],
               "interpretation": (
                   "The Maintainability Index is a transparent composite, not a "
                   "verdict. Read the components: a low MI driven by LOC is a "
                   "split-the-unit problem; one driven by cyclomatic complexity is "
                   "a simplify-the-logic problem.")},
    )


if __name__ == "__main__":
    raise SystemExit(cli_main(analyze, SPEC))
