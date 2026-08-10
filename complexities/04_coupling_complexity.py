"""
Complexity #04 - Coupling Complexity
====================================

What is it?      How tightly units are bound to each other.
Why needed?      Coupling decides what you can move. A unit can be internally
                 simple and still be impossible to extract because forty things
                 call it. Every decomposition, service-extraction and
                 strangler-fig plan is really a coupling argument.
How it works?    Fan-in (who calls me) and fan-out (who I call) per unit, then
                 Henry & Kafura information flow, (fan_in * fan_out)^2. The
                 square is the point: a unit that is both heavily called AND
                 calls widely is a routing hub, and removing it is a project
                 rather than a task. A unit with high fan-in but low fan-out is
                 a leaf utility and is usually harmless.
Input required   units[], call_graph
Output artifact  Coupling Complexity Report (uniform envelope).

Theory: Henry & Kafura 1981, "Software Structure Metrics Based on Information Flow".
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from typing import Any, Dict, Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import Spec, Tree, cli_main, insufficient, level_from, result, worst  # noqa: E402

SPEC = Spec(
    id="coupling_complexity", sno=4, name="Coupling Complexity", tier="coupling",
    requires=["units", "call_graph"], optional=["dependency_graph"],
    summary="Fan-in/fan-out and information flow; decides what can be extracted.",
)

BANDS = (4, 16, 64, 256)   # information flow grows as a square, so bands do too


def _role(fan_in: int, fan_out: int) -> str:
    """Coupling shape matters more than coupling volume."""
    if fan_in >= 3 and fan_out >= 3:
        return "hub"          # everything routes through it; hardest to remove
    if fan_in >= 3:
        return "utility"      # widely used leaf; safe if its contract is stable
    if fan_out >= 5:
        return "orchestrator"  # coordinates many; moves only with its callees
    if fan_in == 0 and fan_out == 0:
        return "isolated"     # free to move, or dead
    return "ordinary"


def analyze(tree_raw: Dict[str, Any]) -> Dict[str, Any]:
    tree = Tree(tree_raw)
    degraded = tree.require(SPEC)

    callers: Dict[str, Set[str]] = defaultdict(set)
    callees: Dict[str, Set[str]] = defaultdict(set)
    for edge in tree.call_edges:
        src, dst = edge.get("from"), edge.get("to")
        if src and dst and src != dst:
            callees[src].add(dst)
            callers[dst].add(src)

    known = {u.get("id") for u in tree.units}

    items = []
    for unit in tree.units:
        uid = unit.get("id")
        fan_in = len(callers.get(uid, ()))
        fan_out = len(callees.get(uid, ()))
        external = len([c for c in callees.get(uid, ()) if c not in known])
        flow = (fan_in * fan_out) ** 2
        role = _role(fan_in, fan_out)

        items.append({
            "unit": uid,
            "name": unit.get("name", uid),
            "owner_type": unit.get("owner_type"),
            "fan_in": fan_in,
            "fan_out": fan_out,
            "external_calls": external,
            "information_flow": flow,
            "role": role,
            "extractable": fan_in <= 2 and fan_out <= 4,
            "score": float(flow),
            "level": level_from(flow, BANDS),
        })

    if not items:
        insufficient("tree contains no units")

    scores = [i["score"] for i in items]
    hubs = [i for i in items if i["role"] == "hub"]
    isolated = [i for i in items if i["role"] == "isolated"]
    extractable = [i for i in items if i["extractable"]]

    # Unresolved callees are holes in the graph. Every coupling number here is a
    # lower bound while they exist, and saying so is the difference between a
    # measurement and a guess.
    unresolved = sorted({c for s in callees.values() for c in s if c not in known})
    confidence = 1.0
    reasons = []
    if unresolved:
        confidence = max(0.6, 1.0 - len(unresolved) / max(len(known), 1))
        reasons.append(
            f"{len(unresolved)} call target(s) not resolved to a known unit - "
            f"fan-out is a lower bound")
    if degraded:
        confidence = min(confidence, 0.9)
        reasons += [f"optional input '{f}' absent" for f in degraded]

    return result(
        SPEC, tree,
        level=worst(i["level"] for i in items),
        score=max(scores),
        headline=(f"{len(items)} unit(s); {len(hubs)} hub(s); "
                  f"{len(extractable)} independently extractable; "
                  f"{len(isolated)} isolated"),
        metrics={
            "units": len(items),
            "call_edges": len(tree.call_edges),
            "max_fan_in": max(i["fan_in"] for i in items),
            "max_fan_out": max(i["fan_out"] for i in items),
            "avg_fan_in": round(sum(i["fan_in"] for i in items) / len(items), 2),
            "avg_fan_out": round(sum(i["fan_out"] for i in items) / len(items), 2),
            "max_information_flow": int(max(scores)),
            "hub_units": len(hubs),
            "utility_units": len([i for i in items if i["role"] == "utility"]),
            "orchestrator_units": len([i for i in items if i["role"] == "orchestrator"]),
            "isolated_units": len(isolated),
            "extractable_units": len(extractable),
            "extractable_ratio": round(len(extractable) / len(items), 3),
            "unresolved_call_targets": len(unresolved),
            "bands_applied": list(BANDS),
        },
        confidence=confidence,
        confidence_reasons=reasons,
        hotspots=sorted(hubs, key=lambda i: -i["score"])[:10],
        items=items,
        extra={
            "roles": {
                "hub": "Called by many AND calls many. Hardest to remove - removing it is a project.",
                "utility": "Called by many, calls few. Safe while its contract holds.",
                "orchestrator": "Calls many. Moves only together with its callees.",
                "isolated": "No inbound or outbound calls. Free to move - or dead code.",
            },
            "unresolved_call_targets": unresolved[:20],
        },
    )


if __name__ == "__main__":
    raise SystemExit(cli_main(analyze, SPEC))
