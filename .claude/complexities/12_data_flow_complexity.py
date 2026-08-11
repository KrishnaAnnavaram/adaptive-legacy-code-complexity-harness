"""
Complexity #12 - Data Flow Complexity
=====================================

What is it?      How much data a unit moves, and how much of it is shared state
                 rather than arguments it was handed.
Why needed?      Control-flow metrics see branching; they are blind to data. A
                 unit can be structurally simple and still be hard to reason about
                 because it reads and writes state nobody passed to it. Shared
                 mutable data is also what makes units impossible to move
                 independently, so this is a decomposition signal as much as a
                 readability one.
How it works?    A def-use style pressure score per unit: parameters in, distinct
                 data elements touched, data passed out through calls, and - the
                 part that hurts - references to data ALSO touched by other units
                 (shared state), which is weighted hardest.
Input required   units[]  with references and/or params  (cfg adds outbound-call cost)
Output artifact  Data Flow Complexity Report (uniform envelope).

LANGUAGE NEUTRALITY
    A "data element" is any identifier the parser recorded a unit as reading or
    writing: a Java field, a COBOL WORKING-STORAGE item, a PL/SQL package
    variable. Shared state is state that appears in more than one unit, in any
    language.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import (  # noqa: E402
    Spec, Tree, cli_main, insufficient, level_from, result, worst,
)

SPEC = Spec(
    id="data_flow_complexity", sno=12, name="Data Flow Complexity", tier="data",
    requires=["units"], requires_any=["references", "params"], optional=["cfg"],
    summary="How much data - especially shared state - each unit moves.",
)

BANDS = (6, 12, 20, 32)


def _count_calls(cfg: Dict[str, Any]) -> int:
    """CALL nodes = points where data is handed out to other units."""
    return Tree.count(cfg, {"CALL"}) if cfg else 0


def analyze(tree_raw: Dict[str, Any]) -> Dict[str, Any]:
    tree = Tree(tree_raw)
    degraded = tree.require(SPEC)

    # How many distinct units reference each data element -> shared state is costly.
    refs_by_data: Dict[str, int] = defaultdict(int)
    for u in tree.units:
        for r in set(u.get("references") or []):
            refs_by_data[r] += 1

    items: List[Dict[str, Any]] = []
    module_scores: Dict[str, float] = defaultdict(float)
    for u in tree.units:
        params = list(u.get("params") or [])
        distinct_refs = set(u.get("references") or [])
        calls = _count_calls(u.get("cfg") or {})
        shared = sum(1 for r in distinct_refs if refs_by_data[r] > 1)

        score = (len(params) * 1.0 + len(distinct_refs) * 1.0
                 + calls * 1.5 + shared * 2.0)
        module_scores[u.get("owner_type") or "<module>"] += score

        items.append({
            "unit": u.get("id"),
            "name": u.get("name", u.get("id")),
            "owner_type": u.get("owner_type"),
            "params_in": len(params),
            "data_refs": len(distinct_refs),
            "shared_data_refs": shared,
            "outbound_calls": calls,
            "score": round(score, 1),
            "level": level_from(score, BANDS),
        })

    if not items:
        insufficient("tree contains no units")

    items.sort(key=lambda i: (-i["score"], i["unit"]))
    max_score = items[0]["score"]
    shared_elements = [d for d, c in refs_by_data.items() if c > 1]
    heavy = [i for i in items if i["level"] in ("L4", "L5")]

    return result(
        SPEC, tree,
        level=worst(i["level"] for i in items),
        score=max_score,
        headline=(f"{len(items)} unit(s); max data-flow score {max_score}; "
                  f"{len(shared_elements)} shared data element(s); "
                  f"{len(heavy)} data-heavy unit(s)"),
        metrics={
            "units": len(items),
            "distinct_data_elements": len(refs_by_data),
            "shared_data_elements": len(shared_elements),
            "max_data_flow_score": max_score,
            "avg_data_flow_score": round(sum(i["score"] for i in items) / len(items), 2),
            "per_module_score": dict(sorted(
                ((k, round(v, 1)) for k, v in module_scores.items()),
                key=lambda kv: -kv[1])[:20]),
            "bands_applied": list(BANDS),
        },
        confidence=1.0 if not degraded else 0.9,
        confidence_reasons=(
            ["cfg absent - data handed out through calls is not counted, so the "
             "score is a lower bound"] if "cfg" in degraded else []),
        hotspots=heavy[:10],
        items=items,
        extra={"interpretation": (
            "shared_data_refs is the part that matters: a unit reading data that "
            "other units also touch is coupled through state, not just through "
            "calls, and cannot be moved without moving that state too."
        )},
    )


if __name__ == "__main__":
    raise SystemExit(cli_main(analyze, SPEC))
