"""
Complexity #11 - Maintainability Complexity  (DERIVED)
======================================================

What is it?      Overall difficulty of maintaining the code over time.
Why needed?      Supports takeover, modernization and technical-debt assessment.
How it works?    Combines size (LOC), logic complexity (cyclomatic), Halstead
                 volume and comment density into the industry Maintainability
                 Index (MI), then derives an L1-L5 level.  Derived transparently
                 from underlying metrics - not invented.
Input required   Underlying static metrics, all read from the Normalized Tree.
Output artifact  Maintainability Report (returned as a dict).

--------------------------------------------------------------------------------
INPUT CONTRACT (subset of the Normalized Tree used here)
--------------------------------------------------------------------------------
tree = {
  "language": "java",
  "units": [ {
       "id","name","loc",
       "cfg": {"node_type","children":[...]},        # for cyclomatic complexity
       "halstead": {"volume": float},                # optional; estimated if absent
       "comment_lines": int                          # optional
  }, ... ]
}

Maintainability Index (Microsoft / SEI variant, clamped to 0-100):
    MI = MAX(0, (171 - 5.2*ln(V) - 0.23*CC - 16.2*ln(LOC)) * 100 / 171)
where V = Halstead volume, CC = cyclomatic complexity, LOC = lines of code.
A comment-density bonus is added (SEI extension).  Higher MI = easier to maintain.
"""

from __future__ import annotations
import math
from typing import Any, Dict, List

# Decision nodes that add to cyclomatic complexity.
_DECISION = {"IF", "ELIF", "FOR", "WHILE", "DO_WHILE", "CASE", "CATCH", "TERNARY", "AND", "OR"}

# MI is "higher = better", so bands run the opposite direction to other analyzers.
# Level = maintenance *complexity*, so low MI => high complexity (L5).
_MI_BANDS = [(85, "L1"), (70, "L2"), (50, "L3"), (30, "L4")]  # else L5


def _level_from_mi(mi: float) -> str:
    for threshold, level in _MI_BANDS:
        if mi >= threshold:
            return level
    return "L5"


def _cyclomatic(cfg: Dict[str, Any]) -> int:
    """Cyclomatic complexity = 1 + number of decision points in the CFG tree."""
    if not cfg:
        return 1
    count = 1
    stack = [cfg]
    while stack:
        node = stack.pop()
        if node.get("node_type") in _DECISION:
            count += 1
        stack.extend(node.get("children", []) or [])
    return count


def _halstead_volume(unit: Dict[str, Any], cc: int, loc: int) -> float:
    """Use provided Halstead volume, else estimate from size & branching."""
    vol = (unit.get("halstead", {}) or {}).get("volume")
    if vol and vol > 0:
        return float(vol)
    # Rough proxy: each LOC contributes operators/operands; branch-heavy code weighs more.
    approx = max(1.0, loc) * (3.0 + 0.5 * cc)
    return approx * math.log2(max(2.0, approx))


def _mi(loc: int, cc: int, volume: float, comment_ratio: float) -> float:
    loc = max(1, loc)
    volume = max(1.0, volume)
    raw = 171 - 5.2 * math.log(volume) - 0.23 * cc - 16.2 * math.log(loc)
    mi = max(0.0, raw) * 100.0 / 171.0
    # SEI comment bonus: up to +50 * a bounded sine term.
    mi += 50.0 * math.sin(math.sqrt(2.4 * comment_ratio))
    return max(0.0, min(100.0, mi))


def analyze(tree: Dict[str, Any]) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    total_loc = 0

    for u in tree.get("units", []):
        loc = int(u.get("loc", 0) or 0)
        total_loc += loc
        cc = _cyclomatic(u.get("cfg") or {})
        volume = _halstead_volume(u, cc, loc)
        comment_lines = int(u.get("comment_lines", 0) or 0)
        comment_ratio = (comment_lines / loc) if loc else 0.0
        mi = _mi(loc, cc, volume, comment_ratio)
        items.append({
            "unit": u["id"],
            "name": u.get("name", u["id"]),
            "loc": loc,
            "cyclomatic": cc,
            "halstead_volume": round(volume, 1),
            "comment_ratio": round(comment_ratio, 3),
            "maintainability_index": round(mi, 1),
            "level": _level_from_mi(mi),
        })

    if items:
        # LOC-weighted mean MI: big units dominate maintainability of the whole.
        weight = sum(max(1, i["loc"]) for i in items)
        weighted_mi = sum(i["maintainability_index"] * max(1, i["loc"]) for i in items) / weight
        worst = min(items, key=lambda i: i["maintainability_index"])
        overall = _level_from_mi(weighted_mi)
        hard = [i for i in items if i["maintainability_index"] < 50]
    else:
        weighted_mi = 100.0
        worst = None
        overall = "L1"
        hard = []

    return {
        "complexity": "Maintainability Complexity",
        "sno": 11,
        "language": tree.get("language", "unknown"),
        "derived_from": ["LOC", "Cyclomatic Complexity", "Halstead Volume", "Comment Density"],
        "summary": {
            "level": overall,
            "score": round(weighted_mi, 1),
            "headline": (f"Weighted Maintainability Index {round(weighted_mi, 1)}/100; "
                         f"{len(hard)} hard-to-maintain unit(s)"),
        },
        "metrics": {
            "units": len(items),
            "total_loc": total_loc,
            "weighted_maintainability_index": round(weighted_mi, 1),
            "worst_unit": worst["unit"] if worst else None,
            "worst_index": worst["maintainability_index"] if worst else None,
            "hard_to_maintain_units": len(hard),
        },
        "hotspots": sorted(hard, key=lambda i: i["maintainability_index"])[:10],
        "items": items,
    }


if __name__ == "__main__":
    import json
    demo = {
        "language": "python",
        "units": [
            {"id": "svc.process", "name": "process", "loc": 220, "comment_lines": 5,
             "cfg": {"node_type": "SEQUENCE", "children": [
                 {"node_type": "FOR", "children": [
                     {"node_type": "IF", "children": [
                         {"node_type": "AND", "children": []}]},
                     {"node_type": "IF", "children": []}]},
                 {"node_type": "WHILE", "children": [{"node_type": "CASE", "children": []}]}]}},
            {"id": "svc.tiny", "name": "tiny", "loc": 8, "comment_lines": 3,
             "cfg": {"node_type": "SEQUENCE", "children": []}},
        ],
    }
    print(json.dumps(analyze(demo), indent=2))
