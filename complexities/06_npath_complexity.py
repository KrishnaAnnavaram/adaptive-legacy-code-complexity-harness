"""
Complexity #06 - NPath Complexity
=================================

What is it?      The number of distinct acyclic execution paths through a unit.
Why needed?      Cyclomatic complexity counts the paths you must test to cover
                 every EDGE. NPath counts the paths that actually EXIST. The two
                 diverge violently: ten sequential if statements give v(G) = 11
                 and NPath = 1,024. That gap is why "we have full branch
                 coverage" and "we tested the combinations" are different
                 claims, and why some units cannot be exhaustively tested at all.
How it works?    Paths multiply through sequence and add through branches.
                 A unit with independent branches b1..bn has PROD(paths(bi)).
Input required   units[].cfg
Output artifact  NPath Complexity Report (uniform envelope).

Theory: Nejmeh 1988, "NPATH: a measure of execution path complexity".

OVERFLOW
    NPath grows multiplicatively and reaches astronomic values on real legacy
    code. Counting is capped at CAP; beyond it the unit is reported as
    `capped: true` with `>= CAP`. An exact figure of 10^47 conveys nothing that
    "beyond exhaustive testing" does not, and computing it invites overflow
    handling bugs for no analytical gain.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import (  # noqa: E402
    LOOP_NODES, Spec, Tree, cli_main, insufficient, level_from, result, worst,
)

SPEC = Spec(
    id="npath_complexity", sno=6, name="NPath Complexity", tier="structural",
    requires=["units", "cfg"],
    summary="Distinct acyclic execution paths; shows what branch coverage misses.",
)

BANDS = (200, 2000, 20000, 200000)
CAP = 10 ** 12

# Paths contributed by one construct, before multiplication.
#   IF          -> 2 (taken / not taken)
#   IF + ELSE   -> 2 (the ELSE child is folded into its parent, not counted again)
#   loop        -> 2 (entered / skipped)
#   CASE arm    -> 1 each, summed by the parent
_PATHS = {"IF": 2, "ELIF": 2, "TERNARY": 2, "AND": 2, "OR": 2, "CATCH": 2}


def _npath(node: Dict[str, Any]) -> int:
    """Multiplicative path count over the CFG subtree.

    Sequence multiplies (every combination of independent choices is a distinct
    path); a construct's own branching factor multiplies in on top.
    """
    if not node:
        return 1

    total = 1
    for child in node.get("children") or []:
        total *= _npath(child)
        if total >= CAP:
            return CAP

    nt = node.get("node_type")
    factor = 1
    if nt in _PATHS:
        factor = _PATHS[nt]
    elif nt in LOOP_NODES:
        factor = 2                      # entered at least once, or skipped
    elif nt == "CASE":
        # Each arm is a distinct path; a CASE with n arms contributes n, not 2.
        arms = len([c for c in (node.get("children") or [])
                    if c.get("node_type") not in ("DEFAULT",)])
        factor = max(2, arms)

    total *= factor
    return min(total, CAP)


def analyze(tree_raw: Dict[str, Any]) -> Dict[str, Any]:
    tree = Tree(tree_raw)
    tree.require(SPEC)

    items = []
    for unit in tree.units:
        cfg = unit.get("cfg") or {}
        paths = _npath(cfg)
        capped = paths >= CAP
        vg = Tree.cyclomatic(cfg)

        # The ratio is the real finding: how much combinatorial surface hides
        # behind a comfortable-looking v(G).
        ratio = round(paths / vg, 1) if vg else 0.0

        items.append({
            "unit": unit.get("id"),
            "name": unit.get("name", unit.get("id")),
            "owner_type": unit.get("owner_type"),
            "start_line": unit.get("start_line"),
            "npath": paths if not capped else None,
            "npath_display": f">= {CAP:,}" if capped else f"{paths:,}",
            "capped": capped,
            "cyclomatic": vg,
            "paths_per_branch_test": ratio,
            "exhaustively_testable": paths <= 2000,
            "score": float(min(paths, BANDS[-1] * 10)),
            "level": level_from(paths, BANDS),
        })

    if not items:
        insufficient("tree contains no units")

    untestable = [i for i in items if not i["exhaustively_testable"]]
    capped_units = [i for i in items if i["capped"]]
    max_display = max(items, key=lambda i: (i["capped"], i["npath"] or 0))

    return result(
        SPEC, tree,
        level=worst(i["level"] for i in items),
        score=max(i["score"] for i in items),
        headline=(f"{len(items)} unit(s); worst NPath {max_display['npath_display']}; "
                  f"{len(untestable)} unit(s) beyond exhaustive path testing"),
        metrics={
            "units": len(items),
            "max_npath": max_display["npath_display"],
            "units_beyond_exhaustive_testing": len(untestable),
            "units_capped": len(capped_units),
            "exhaustively_testable_ratio": round(
                1 - len(untestable) / len(items), 3),
            "max_paths_per_branch_test": max(i["paths_per_branch_test"] for i in items),
            "cap": CAP,
            "bands_applied": list(BANDS),
        },
        confidence=0.85,
        confidence_reasons=[
            "path counting assumes branches are independent; correlated conditions "
            "make the true reachable count lower, so NPath is an upper bound"
        ],
        hotspots=sorted(untestable,
                        key=lambda i: (i["capped"], i["npath"] or 0), reverse=True)[:10],
        items=items,
        extra={"interpretation": (
            "paths_per_branch_test is the gap between 'we covered every branch' and "
            "'we covered the combinations'. A unit at v(G) 11 with NPath 1,024 is fully "
            "branch-covered by 11 tests and has 1,013 untested combinations."
        )},
    )


if __name__ == "__main__":
    raise SystemExit(cli_main(analyze, SPEC))
