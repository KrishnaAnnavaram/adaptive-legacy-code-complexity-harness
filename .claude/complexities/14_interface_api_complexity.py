"""
Complexity #14 - Interface / API Complexity
===========================================

What is it?      The size and shape of the contract a system exposes - its
                 interfaces, endpoints, operations and their payloads.
Why needed?      The exposed surface is what other systems couple to, and it is
                 the most expensive thing to change because you cannot see all the
                 callers. In integration-heavy and microservice estates it is the
                 surface that decides migration and versioning cost, and it is
                 invisible to every per-unit control-flow metric.
How it works?    Identifies exposed operations (methods of interface types, or
                 units the parser flagged as exposed / HTTP-bound), then scores
                 breadth (how many operations), depth (parameters per operation),
                 payload weight (distinct schemas/DTOs) and integration count
                 (api-kind dependency edges).
Input required   units[]  with types (interfaces) and/or params  (meta / deps refine it)
Output artifact  API Complexity Report (uniform envelope).

LANGUAGE NEUTRALITY
    An "exposed operation" is whatever the adapter marks as such: a Java interface
    method or @RestController mapping, a PL/SQL package's public procedures, a
    COBOL program's linkage-section entry points. Scoring reads only the neutral
    signals (interface membership, parameter counts, meta bindings).
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import (  # noqa: E402
    Spec, Tree, cli_main, level_from, result,
)

SPEC = Spec(
    id="interface_api_complexity", sno=14, name="Interface / API Complexity",
    tier="coupling", requires=["units"], requires_any=["types", "params"],
    optional=["meta", "dependency_graph"], scope="tree",
    summary="Size and shape of the exposed contract surface.",
)

BANDS = (15, 35, 55, 75)          # blended API-surface score, 0-100


def analyze(tree_raw: Dict[str, Any]) -> Dict[str, Any]:
    tree = Tree(tree_raw)
    degraded = tree.require(SPEC)

    units = {u.get("id"): u for u in tree.units}

    # Methods belonging to an interface/abstract type are exposed operations.
    interface_methods = set()
    for t in tree.types:
        if (t.get("kind") or "").lower() in ("interface", "abstract") \
                or (t.get("meta") or {}).get("exposed"):
            interface_methods.update(t.get("methods") or [])

    operations: List[Dict[str, Any]] = []
    schemas: set = set()
    for uid, u in units.items():
        meta = u.get("meta") or {}
        exposed = (uid in interface_methods or meta.get("exposed")
                   or bool(meta.get("http")))
        if not exposed:
            continue
        params = list(u.get("params") or [])
        op_schemas = list(meta.get("schemas") or [])
        schemas.update(op_schemas)
        op_score = len(params) + 1.5 * len(op_schemas)
        operations.append({
            "operation": uid,
            "name": u.get("name", uid),
            "owner_type": u.get("owner_type"),
            "binding": meta.get("http", ""),
            "params": len(params),
            "schemas": len(op_schemas),
            "op_score": round(op_score, 1),
            "level": level_from(min(100.0, op_score * 6), BANDS),
        })

    # No exposed operations is a genuine zero, not an absence: given types and
    # params were present (the gate), a system that exposes no interface/endpoint
    # (e.g. a batch program) truly has no contract surface. Report it as L1, not
    # insufficient_input - collapsing "measured zero surface" into "not measured"
    # would hide a real architectural fact.
    if not operations:
        return result(
            SPEC, tree,
            level="L1", score=0.0,
            headline="no exposed operations - system presents no interface/API surface",
            metrics={"exposed_operations": 0, "bands_applied": list(BANDS)},
            confidence=1.0,
            items=[],
            extra={"interpretation": (
                "No interface types and no exposed/HTTP markers were found. This is a "
                "measured absence of an API surface (e.g. a batch or library-internal "
                "module), not a gap in the input.")},
        )

    dep_edges = (tree.raw.get("dependency_graph") or {}).get("edges") or []
    api_contracts = [e for e in dep_edges if (e.get("kind") or "").lower() == "api"]

    n_ops = len(operations)
    total_params = sum(o["params"] for o in operations)
    avg_params = round(total_params / n_ops, 2) if n_ops else 0.0
    max_params = max((o["params"] for o in operations), default=0)

    score = min(100.0, (
        min(n_ops, 40) / 40 * 40
        + min(avg_params, 8) / 8 * 20
        + min(len(schemas), 30) / 30 * 20
        + min(len(api_contracts), 20) / 20 * 20
    ))

    operations.sort(key=lambda o: (-o["op_score"], o["operation"]))
    heavy_ops = [o for o in operations if o["params"] >= 5 or o["schemas"] >= 3]

    # Payload/binding detail only exists if the parser carried `meta`. Without it
    # the surface is measured from interface membership and arity alone.
    have_meta = tree.has("meta")
    confidence = 1.0
    reasons: List[str] = []
    if not have_meta:
        confidence = 0.85
        reasons.append("no unit `meta` - schemas and HTTP bindings unavailable, so "
                       "payload weight and endpoint detail are not counted")

    return result(
        SPEC, tree,
        level=level_from(score, BANDS),
        score=round(score, 1),
        headline=(f"{n_ops} exposed operation(s); avg {avg_params} param(s)/op; "
                  f"{len(schemas)} schema(s); {len(api_contracts)} external API contract(s)"),
        metrics={
            "exposed_operations": n_ops,
            "total_parameters": total_params,
            "avg_params_per_op": avg_params,
            "max_params_in_op": max_params,
            "distinct_schemas": len(schemas),
            "external_api_contracts": len(api_contracts),
            "heavy_operations": len(heavy_ops),
            "bands_applied": list(BANDS),
        },
        confidence=confidence,
        confidence_reasons=reasons,
        hotspots=heavy_ops[:10],
        items=operations,
        extra={"interpretation": (
            "Surface is breadth x depth: many operations, wide parameter lists and "
            "heavy payloads each multiply the cost of a contract change, because "
            "every consumer must be found and re-tested."
        )},
    )


if __name__ == "__main__":
    raise SystemExit(cli_main(analyze, SPEC))
