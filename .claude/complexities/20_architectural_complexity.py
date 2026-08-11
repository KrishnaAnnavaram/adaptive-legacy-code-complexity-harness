"""
Complexity #20 - Architectural Complexity
=========================================

What is it?      Structural quality of the system ABOVE the unit: how modules
                 depend on each other, whether layers hold, and where the seams
                 are.
Why needed?      Every other analyzer scores units. None of them answers the
                 question a modernization programme actually starts with: can
                 this be decomposed, and where do we cut? A codebase of clean
                 units can still be architecturally unsplittable, and a codebase
                 of ugly units can decompose cleanly along good module lines.
How it works?    Four independent structural signals, each with a different
                 remedy:
                   1. DEPENDENCY CYCLES - modules that cannot be extracted
                      separately, at any cost, until the cycle is broken.
                   2. INSTABILITY / ABSTRACTNESS (Martin) - modules in the
                      "zone of pain" (concrete and heavily depended upon) and
                      the "zone of uselessness" (abstract and depended on by
                      nobody).
                   3. LAYERING VIOLATIONS - edges that skip or invert the
                      declared layer order.
                   4. GOD UNITS AND HUBS - single points that everything routes
                      through, whose removal is a project in itself.
Input required   Normalized Tree: dependency_graph, call_graph, units, types.
Output artifact  Architectural Complexity Report (returned as a dict).

--------------------------------------------------------------------------------
INPUT CONTRACT (subset of the Normalized Tree used here)
--------------------------------------------------------------------------------
tree = {
  "language": "java",
  "units": [ {"id","name","owner_type"}, ... ],
  "types": [ {"id","name","kind":"class|interface|abstract|record"}, ... ],  # optional
  "call_graph":       {"nodes":[unit_id,...], "edges":[{"from","to"}, ...]},
  "dependency_graph": {
      "nodes": [module_id, ...],
      "edges": [ {"from":module_id,"to":module_id,
                  "kind":"internal|external|library|api|db|platform|config"}, ... ]
  },
  "layers": {"presentation":0, "service":1, "domain":2, "data":3},   # optional
  "module_layer": {"module_id": "service", ...}                       # optional
}

MARTIN'S METRICS (1994), computed per module:
    Ca = afferent coupling  - modules that depend on this one
    Ce = efferent coupling  - modules this one depends on
    I  = Ce / (Ca + Ce)     - instability,  0 = maximally stable
    A  = abstract types / total types  - abstractness
    D  = |A + I - 1|        - distance from the main sequence

    Zone of pain       : low I, low A  - concrete and widely depended upon.
                         Expensive to change, and everything breaks when you do.
    Zone of uselessness: high A, high I - abstract and nothing depends on it.

LANGUAGE NEUTRALITY
    "Module" is whatever the adapter says it is: a Java package, a PL/SQL
    package or schema, a COBOL program or copybook group. Abstractness needs a
    type system, so it is reported as null for languages without one rather
    than being faked as zero - a COBOL program is not "0% abstract", the
    concept does not apply.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple

# Calibration on the system-level architectural score.
_BANDS = [(10, "L1"), (22, "L2"), (40, "L3"), (65, "L4")]  # else L5

_ABSTRACT_KINDS = {"interface", "abstract", "protocol", "trait"}


def _calibrate(score: float) -> str:
    for threshold, level in _BANDS:
        if score <= threshold:
            return level
    return "L5"


def _find_cycles(nodes: Set[str], edges: List[Tuple[str, str]]) -> List[List[str]]:
    """Strongly connected components with more than one member, via Tarjan.

    Iterative rather than recursive: legacy dependency graphs are wide and deep
    enough to blow Python's recursion limit, and a crashed analyzer reports
    nothing at all.
    """
    graph: Dict[str, List[str]] = defaultdict(list)
    for src, dst in edges:
        graph[src].append(dst)

    index_counter = [0]
    index: Dict[str, int] = {}
    lowlink: Dict[str, int] = {}
    on_stack: Dict[str, bool] = {}
    stack: List[str] = []
    result: List[List[str]] = []

    for root in sorted(nodes):
        if root in index:
            continue
        work: List[Tuple[str, int]] = [(root, 0)]
        while work:
            node, pi = work[-1]
            if pi == 0:
                index[node] = lowlink[node] = index_counter[0]
                index_counter[0] += 1
                stack.append(node)
                on_stack[node] = True

            recursed = False
            successors = graph.get(node, [])
            for i in range(pi, len(successors)):
                nxt = successors[i]
                work[-1] = (node, i + 1)
                if nxt not in index:
                    work.append((nxt, 0))
                    recursed = True
                    break
                if on_stack.get(nxt):
                    lowlink[node] = min(lowlink[node], index[nxt])
            if recursed:
                continue

            if lowlink[node] == index[node]:
                component: List[str] = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    component.append(w)
                    if w == node:
                        break
                if len(component) > 1:
                    result.append(sorted(component))

            work.pop()
            if work:
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])

    return result


def _module_of(unit: Dict[str, Any]) -> str:
    return unit.get("owner_type") or unit.get("module") or "UNASSIGNED"


def analyze(tree: Dict[str, Any]) -> Dict[str, Any]:
    units = tree.get("units", []) or []
    types = tree.get("types", []) or []
    dep = tree.get("dependency_graph") or {}
    call = tree.get("call_graph") or {}

    dep_edges_raw = dep.get("edges") or []
    internal_edges = [
        (e.get("from"), e.get("to")) for e in dep_edges_raw
        if e.get("from") and e.get("to")
        and (e.get("kind") or "internal").lower() in ("internal", "api", "")
    ]
    all_dep_edges = [(e.get("from"), e.get("to")) for e in dep_edges_raw
                     if e.get("from") and e.get("to")]

    modules: Set[str] = set(dep.get("nodes") or [])
    modules |= {m for edge in all_dep_edges for m in edge}
    modules |= {_module_of(u) for u in units}
    modules.discard(None)

    # ---- 1. Dependency cycles -------------------------------------------
    cycles = _find_cycles(modules, internal_edges)
    modules_in_cycles = {m for c in cycles for m in c}

    # ---- 2. Martin metrics ----------------------------------------------
    ca: Dict[str, Set[str]] = defaultdict(set)
    ce: Dict[str, Set[str]] = defaultdict(set)
    for src, dst in all_dep_edges:
        if src != dst:
            ce[src].add(dst)
            ca[dst].add(src)

    types_by_module: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in types:
        owner = t.get("module") or t.get("owner_type") or t.get("package")
        if owner:
            types_by_module[owner].append(t)

    has_type_system = bool(types)

    module_items: List[Dict[str, Any]] = []
    for module in sorted(modules):
        n_ca, n_ce = len(ca.get(module, ())), len(ce.get(module, ()))
        instability = (n_ce / (n_ca + n_ce)) if (n_ca + n_ce) else None

        mod_types = types_by_module.get(module, [])
        if has_type_system and mod_types:
            abstract = len([t for t in mod_types
                            if (t.get("kind") or "").lower() in _ABSTRACT_KINDS])
            abstractness = abstract / len(mod_types)
        else:
            # Not zero - the concept does not apply without a type system.
            abstractness = None

        distance = (abs(abstractness + instability - 1)
                    if abstractness is not None and instability is not None else None)

        zone = None
        if abstractness is not None and instability is not None:
            if instability <= 0.3 and abstractness <= 0.3 and n_ca >= 2:
                zone = "pain"
            elif instability >= 0.7 and abstractness >= 0.7:
                zone = "uselessness"
            elif distance is not None and distance <= 0.2:
                zone = "main_sequence"

        unit_count = len([u for u in units if _module_of(u) == module])

        module_items.append({
            "module": module,
            "units": unit_count,
            "afferent_coupling": n_ca,
            "efferent_coupling": n_ce,
            "instability": round(instability, 3) if instability is not None else None,
            "abstractness": round(abstractness, 3) if abstractness is not None else None,
            "distance_from_main_sequence": round(distance, 3) if distance is not None else None,
            "zone": zone,
            "in_cycle": module in modules_in_cycles,
        })

    # ---- 3. Layering violations -----------------------------------------
    layers = tree.get("layers") or {}
    module_layer = tree.get("module_layer") or {}
    violations: List[Dict[str, Any]] = []
    if layers and module_layer:
        for src, dst in all_dep_edges:
            src_layer, dst_layer = module_layer.get(src), module_layer.get(dst)
            if src_layer is None or dst_layer is None:
                continue
            src_rank, dst_rank = layers.get(src_layer), layers.get(dst_layer)
            if src_rank is None or dst_rank is None:
                continue
            if dst_rank < src_rank:
                violations.append({
                    "from": src, "to": dst,
                    "from_layer": src_layer, "to_layer": dst_layer,
                    "kind": "inverted",
                    "detail": f"{src_layer} depends on {dst_layer} - dependency points upward",
                })
            elif dst_rank - src_rank > 1:
                violations.append({
                    "from": src, "to": dst,
                    "from_layer": src_layer, "to_layer": dst_layer,
                    "kind": "skipped",
                    "detail": f"{src_layer} reaches past {dst_rank - src_rank - 1} layer(s) to {dst_layer}",
                })

    # ---- 4. God units and hubs ------------------------------------------
    call_edges = call.get("edges") or []
    unit_fan_in: Dict[str, int] = defaultdict(int)
    unit_fan_out: Dict[str, int] = defaultdict(int)
    for e in call_edges:
        if e.get("from") and e.get("to"):
            unit_fan_out[e["from"]] += 1
            unit_fan_in[e["to"]] += 1

    names = {u.get("id"): u.get("name", u.get("id")) for u in units}
    all_unit_ids = set(names) | set(unit_fan_in) | set(unit_fan_out)
    god_units = []
    for uid in sorted(all_unit_ids):
        fi, fo = unit_fan_in.get(uid, 0), unit_fan_out.get(uid, 0)
        # Henry & Kafura information flow: (fan-in x fan-out)^2. The square is
        # the point - a unit that is both heavily called AND calls widely is a
        # routing hub, and removing it is a project rather than a task.
        flow = (fi * fo) ** 2
        if fi >= 3 and fo >= 3:
            god_units.append({
                "unit": uid, "name": names.get(uid, uid),
                "fan_in": fi, "fan_out": fo, "information_flow": flow,
            })
    god_units.sort(key=lambda g: -g["information_flow"])

    # ---- system score ----------------------------------------------------
    # Cycles dominate. A cyclic module group cannot be extracted separately at
    # any price until the cycle is broken, so it is a hard blocker rather than
    # a quality signal.
    s_cycles = sum(len(c) * 6.0 for c in cycles)
    s_pain = len([m for m in module_items if m["zone"] == "pain"]) * 5.0
    s_violations = sum(6.0 if v["kind"] == "inverted" else 3.0 for v in violations)
    s_gods = min(len(god_units) * 3.0, 25.0)
    avg_ce = (sum(m["efferent_coupling"] for m in module_items) / len(module_items)
              if module_items else 0.0)
    s_coupling = min(avg_ce * 1.5, 20.0)

    score = s_cycles + s_pain + s_violations + s_gods + s_coupling
    overall = _calibrate(score)

    caveats: List[str] = []
    if not dep_edges_raw:
        caveats.append(
            "No dependency_graph edges - cycles, coupling and layering are unmeasured. "
            "Module-level architecture cannot be assessed from unit data alone."
        )
    if not has_type_system:
        caveats.append(
            "No type information - abstractness and distance-from-main-sequence are "
            "reported as null rather than zero. Martin's zones do not apply to "
            "languages without a type system."
        )
    if not (layers and module_layer):
        caveats.append(
            "No layer declaration - layering violations not checked. Supply `layers` "
            "and `module_layer` to enable this dimension."
        )

    return {
        "complexity": "Architectural Complexity",
        "sno": 20,
        "language": tree.get("language", "unknown"),
        "summary": {
            "level": overall,
            "score": round(score, 1),
            "headline": (
                f"{len(modules)} module(s); {len(cycles)} dependency cycle(s) covering "
                f"{len(modules_in_cycles)} module(s); {len(violations)} layering violation(s); "
                f"{len(god_units)} hub unit(s)"
            ),
        },
        "metrics": {
            "modules": len(modules),
            "dependency_edges": len(all_dep_edges),
            "dependency_cycles": len(cycles),
            "modules_in_cycles": len(modules_in_cycles),
            "layering_violations": len(violations),
            "inverted_dependencies": len([v for v in violations if v["kind"] == "inverted"]),
            "skipped_layers": len([v for v in violations if v["kind"] == "skipped"]),
            "modules_in_zone_of_pain": len([m for m in module_items if m["zone"] == "pain"]),
            "modules_in_zone_of_uselessness": len([m for m in module_items if m["zone"] == "uselessness"]),
            "modules_on_main_sequence": len([m for m in module_items if m["zone"] == "main_sequence"]),
            "god_units": len(god_units),
            "avg_efferent_coupling": round(avg_ce, 2),
            "max_afferent_coupling": max((m["afferent_coupling"] for m in module_items), default=0),
            "architectural_score": round(score, 1),
        },
        "dimension_scores": {
            "dependency_cycles": round(s_cycles, 1),
            "zone_of_pain": round(s_pain, 1),
            "layering_violations": round(s_violations, 1),
            "hub_units": round(s_gods, 1),
            "coupling_density": round(s_coupling, 1),
        },
        "cycles": [{"modules": c, "size": len(c)} for c in
                   sorted(cycles, key=lambda c: -len(c))[:10]],
        "layering_violations": violations[:20],
        "god_units": god_units[:10],
        "decomposition_guidance": (
            "Break dependency cycles first - modules inside a cycle cannot be extracted "
            "independently at any cost. Then address zone-of-pain modules, which are "
            "concrete and widely depended upon and will resist every change. Hub units "
            "are the natural seams once the cycles are gone."
        ),
        "caveats": caveats,
        "hotspots": sorted(
            [m for m in module_items if m["in_cycle"] or m["zone"] == "pain"],
            key=lambda m: (-m["afferent_coupling"], m["module"]),
        )[:10],
        "items": module_items,
    }

# --------------------------------------------------------------------------
# Portable contract (see _core.py). SPEC lets a harness discover, gate and
# order this analyzer without hardcoding anything about it. cli_main enforces
# the declared inputs BEFORE analyze() runs, so a starved analyzer reports
# insufficient_input instead of a misleading zero.
# --------------------------------------------------------------------------
import os as _os  # noqa: E402
import sys as _sys  # noqa: E402

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

from _core import Spec as _Spec, cli_main as _cli_main  # noqa: E402

SPEC = _Spec(
    id='architectural_complexity',
    sno=20,
    name='Architectural Complexity',
    tier='coupling',
    requires=['dependency_graph'],
    optional=['types', 'call_graph', 'layers', 'units'],
    scope='tree',
    summary='Dependency cycles, Martin zones, layering violations and hubs.'
)

if __name__ == "__main__":
    raise SystemExit(_cli_main(analyze, SPEC))
