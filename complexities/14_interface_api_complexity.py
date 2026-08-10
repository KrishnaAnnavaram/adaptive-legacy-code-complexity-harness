"""
Complexity #14 - Interface / API Complexity
===========================================

What is it?      Complexity of the interfaces, endpoints and contracts a system
                 exposes.
Why needed?      Important for microservices and integration-heavy applications -
                 wide/heavy contracts are costly to change and integrate against.
How it works?    Counts exposed operations (public interface/endpoint methods),
                 parameters per operation, distinct schemas/DTOs referenced, and
                 upstream/downstream (api) contract edges.
Input required   API definitions / interface metadata from the Normalized Tree.
Output artifact  API Complexity Report (returned as a dict).

--------------------------------------------------------------------------------
INPUT CONTRACT (subset of the Normalized Tree used here)
--------------------------------------------------------------------------------
tree = {
  "language": "java",
  "units": [ {
      "id","name","owner_type",
      "params": [name, ...],
      "meta": {"exposed": true, "http": "POST /orders", "schemas": [dto_id,...]}  # optional
  }, ... ],
  "types": [ {"id","name","kind","methods":[unit_id,...]} ],   # kind == "interface" => exposed
  "dependency_graph": {"edges":[{"from","to","kind":"api"}, ...]}   # api = external contracts
}

An operation is treated as "exposed" if its owner type is an interface, or its
unit meta says exposed / has an http binding.
"""

from __future__ import annotations
from typing import Any, Dict, List

# Calibration on a blended API-surface score (0-100).
_BANDS = [(15, "L1"), (35, "L2"), (55, "L3"), (75, "L4")]  # else L5


def _calibrate(score: float) -> str:
    for threshold, level in _BANDS:
        if score <= threshold:
            return level
    return "L5"


def analyze(tree: Dict[str, Any]) -> Dict[str, Any]:
    units = {u["id"]: u for u in tree.get("units", [])}
    types = tree.get("types", [])

    # Which unit ids are exposed operations?
    interface_methods = set()
    for t in types:
        if t.get("kind") in ("interface", "abstract") or t.get("meta", {}).get("exposed"):
            interface_methods.update(t.get("methods", []))

    operations: List[Dict[str, Any]] = []
    schemas: set = set()
    for uid, u in units.items():
        meta = u.get("meta", {}) or {}
        exposed = uid in interface_methods or meta.get("exposed") or bool(meta.get("http"))
        if not exposed:
            continue
        params = list(u.get("params", []) or [])
        op_schemas = list(meta.get("schemas", []) or [])
        schemas.update(op_schemas)
        # Per-operation cost: parameter count + schema payload weight.
        op_score = len(params) + 1.5 * len(op_schemas)
        operations.append({
            "operation": uid,
            "name": u.get("name", uid),
            "binding": meta.get("http", ""),
            "params": len(params),
            "schemas": len(op_schemas),
            "op_score": round(op_score, 1),
            "level": _calibrate(min(100, op_score * 6)),
        })

    # api-kind dependency edges = external contracts this system talks to.
    dep_edges = tree.get("dependency_graph", {}).get("edges", []) or []
    api_contracts = [e for e in dep_edges if e.get("kind") == "api"]

    n_ops = len(operations)
    total_params = sum(o["params"] for o in operations)
    avg_params = round(total_params / n_ops, 2) if n_ops else 0.0
    max_params = max((o["params"] for o in operations), default=0)

    # Blended surface score (0-100): breadth (#ops) + depth (params) + payloads + integrations.
    score = min(100.0, (
        min(n_ops, 40) / 40 * 40 +
        min(avg_params, 8) / 8 * 20 +
        min(len(schemas), 30) / 30 * 20 +
        min(len(api_contracts), 20) / 20 * 20
    ))

    operations.sort(key=lambda o: o["op_score"], reverse=True)
    heavy_ops = [o for o in operations if o["params"] >= 5 or o["schemas"] >= 3]

    return {
        "complexity": "Interface / API Complexity",
        "sno": 14,
        "language": tree.get("language", "unknown"),
        "summary": {
            "level": _calibrate(score),
            "score": round(score, 1),
            "headline": (f"{n_ops} exposed operation(s), {len(schemas)} schema(s), "
                         f"{len(api_contracts)} external API contract(s)"),
        },
        "metrics": {
            "exposed_operations": n_ops,
            "total_parameters": total_params,
            "avg_params_per_op": avg_params,
            "max_params_in_op": max_params,
            "distinct_schemas": len(schemas),
            "external_api_contracts": len(api_contracts),
            "heavy_operations": len(heavy_ops),
        },
        "hotspots": heavy_ops[:10],
        "items": operations,
    }


if __name__ == "__main__":
    import json
    demo = {
        "language": "java",
        "units": [
            {"id": "OrderApi.create", "name": "create", "owner_type": "OrderApi",
             "params": ["customerId", "items", "coupon", "address", "payment"],
             "meta": {"http": "POST /orders", "schemas": ["OrderDTO", "AddressDTO"]}},
            {"id": "OrderApi.get", "name": "get", "owner_type": "OrderApi",
             "params": ["id"], "meta": {"http": "GET /orders/{id}", "schemas": ["OrderDTO"]}},
        ],
        "types": [{"id": "OrderApi", "name": "OrderApi", "kind": "interface",
                   "methods": ["OrderApi.create", "OrderApi.get"]}],
        "dependency_graph": {"edges": [{"from": "OrderApi", "to": "PaymentGateway", "kind": "api"}]},
    }
    print(json.dumps(analyze(demo), indent=2))
