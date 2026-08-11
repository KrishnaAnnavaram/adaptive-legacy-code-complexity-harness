"""
Complexity #08 - Cohesion Complexity
====================================

What is it?      Whether the members of a type belong together, or whether the
                 type is several unrelated responsibilities sharing a name.
Why needed?      Low cohesion is the cheapest structural argument for splitting a
                 type. A type whose methods touch disjoint sets of fields is
                 really N types in a trench coat, and every change to one
                 responsibility risks the others. It is the signal that a
                 decomposition seam runs THROUGH a type rather than around it.
How it works?    LCOM4: build a graph whose nodes are the type's methods, join
                 two methods that share a field OR call one another, and count the
                 connected components. One component = cohesive; N components = N
                 latent types. LCOM-HS (Henderson-Sellers, 0..1) is reported
                 alongside as a normalized second opinion.
Input required   units[].references, types[]  (call_graph strengthens the link test)
Output artifact  Cohesion Complexity Report (uniform envelope).

Theory: Hitz & Montazeri 1995 (LCOM4); Henderson-Sellers 1996 (LCOM-HS).

LANGUAGE NEUTRALITY
    "Type" is whatever groups routines and state: a Java/C# class, a PL/SQL
    package, a COBOL program's paragraphs over WORKING-STORAGE. "Fields" are the
    shared data the parser attached to the type. The rule never names a language.
"""

from __future__ import annotations

import os
import sys
from itertools import combinations
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import (  # noqa: E402
    Spec, Tree, cli_main, insufficient, level_from, result, worst,
)

SPEC = Spec(
    id="cohesion_complexity", sno=8, name="Cohesion Complexity", tier="coupling",
    requires=["units", "types"], requires_any=["references", "call_graph"],
    scope="type",
    summary="Whether a type's members belong together (LCOM4 / LCOM-HS).",
)

# LCOM4 = number of connected components of methods. 1 is cohesive; the higher
# the value the more the type is really several types wanting to be split.
BANDS = (1, 2, 3, 5)


class _DSU:
    """Union-find for LCOM4 connected components."""

    def __init__(self, items: List[str]) -> None:
        self.parent = {i: i for i in items}

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb

    def components(self) -> int:
        return len({self.find(x) for x in self.parent})


def _score_type(t: Dict[str, Any], unit_refs: Dict[str, set], call_pairs: set) -> Dict[str, Any]:
    method_ids = [m for m in (t.get("methods") or []) if m in unit_refs]
    fields = set(t.get("fields") or [])
    n = len(method_ids)

    if n <= 1:
        # A type with 0 or 1 method is trivially cohesive - one thing to hold.
        return {
            "type_id": t.get("id"), "name": t.get("name", t.get("id")),
            "kind": t.get("kind", "class"), "methods": n, "fields": len(fields),
            "lcom4": 1, "lcom_hs": 0.0, "shared_pairs": 0, "total_pairs": 0,
            "score": 1.0, "level": "L1",
        }

    dsu = _DSU(method_ids)
    shared_pairs = 0
    total_pairs = 0
    for a, b in combinations(method_ids, 2):
        total_pairs += 1
        shares_field = bool(unit_refs[a] & unit_refs[b] & fields)
        linked_by_call = (a, b) in call_pairs or (b, a) in call_pairs
        if shares_field or linked_by_call:
            dsu.union(a, b)
            if shares_field:
                shared_pairs += 1
    lcom4 = dsu.components()

    if fields:
        accesses = sum(len(unit_refs[m] & fields) for m in method_ids)
        mean_access = accesses / len(fields)          # avg methods touching a field
        denom = (1 - n)
        lcom_hs = (mean_access - n) / denom if denom else 0.0
        lcom_hs = max(0.0, min(1.0, lcom_hs))
    else:
        lcom_hs = 1.0                                  # methods but no shared state

    return {
        "type_id": t.get("id"), "name": t.get("name", t.get("id")),
        "kind": t.get("kind", "class"), "methods": n, "fields": len(fields),
        "lcom4": lcom4, "lcom_hs": round(lcom_hs, 3),
        "shared_pairs": shared_pairs, "total_pairs": total_pairs,
        "score": float(lcom4), "level": level_from(lcom4, BANDS),
    }


def analyze(tree_raw: Dict[str, Any]) -> Dict[str, Any]:
    tree = Tree(tree_raw)
    degraded = tree.require(SPEC)

    unit_refs = {u.get("id"): set(u.get("references") or []) for u in tree.units}
    call_pairs = {(e.get("from"), e.get("to")) for e in tree.call_edges}

    items = [_score_type(t, unit_refs, call_pairs) for t in tree.types]
    if not items:
        insufficient("tree carries no types to assess cohesion")

    scores = [i["score"] for i in items]
    worst_lcom4 = max(scores)
    low_cohesion = [i for i in items if i["lcom4"] >= 3]

    # Cohesion is measured from two signals; with only one present it is a lower
    # bound (a missing signal can only merge components, never split them).
    have_refs = tree.has("references")
    have_calls = bool(call_pairs)
    confidence = 1.0
    reasons: List[str] = []
    if not (have_refs and have_calls):
        confidence = 0.8
        present = "call graph only" if have_calls else "field references only"
        reasons.append(
            f"cohesion linked from {present}; the other signal is absent, so LCOM4 "
            f"is an upper bound on the number of components (a lower bound on cohesion)")

    return result(
        SPEC, tree,
        level=worst(i["level"] for i in items),
        score=worst_lcom4,
        headline=(f"{len(items)} type(s); worst LCOM4 {int(worst_lcom4)}; "
                  f"{len(low_cohesion)} type(s) with low cohesion (>=3 components)"),
        metrics={
            "types": len(items),
            "worst_lcom4": int(worst_lcom4),
            "avg_lcom4": round(sum(scores) / len(items), 2),
            "avg_lcom_hs": round(sum(i["lcom_hs"] for i in items) / len(items), 3),
            "low_cohesion_types": len(low_cohesion),
            "bands_applied": list(BANDS),
        },
        confidence=confidence,
        confidence_reasons=reasons,
        hotspots=sorted(low_cohesion, key=lambda i: -i["lcom4"])[:10],
        items=items,
        extra={"interpretation": (
            "LCOM4 is the number of independent method clusters in a type. A value "
            "of N means the type can be split into N smaller types along the lines "
            "its own methods already draw - each cluster shares state the others do not."
        )},
    )


if __name__ == "__main__":
    raise SystemExit(cli_main(analyze, SPEC))
