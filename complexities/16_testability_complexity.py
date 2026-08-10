"""
Complexity #16 - Testability Complexity
=======================================

What is it?      How hard it is to get a unit under test at all - and how many
                 tests it would then take to cover it.
Why needed?      Modernization is only safe behind a characterization-test net.
                 Testability decides whether that net can be built, and it is
                 the metric that most reliably predicts the true cost of a
                 legacy rewrite. Two units with identical cyclomatic complexity
                 can differ by an order of magnitude in test effort.
How it works?    Separates the two things people conflate:
                   (a) TEST BURDEN  - how many paths need covering (cyclomatic).
                   (b) TEST FRICTION - what stands between you and invoking the
                       unit in isolation: hidden inputs, side effects, hard
                       dependencies that need mocking, non-determinism, and
                       missing seams.
                 Burden is linear and predictable. Friction is what actually
                 blocks a test being written, so it is weighted far harder.
Input required   Normalized Tree: cfg, params, references, call_graph, and any
                 side-effect / dependency signals the parser carried.
Output artifact  Testability Complexity Report (returned as a dict).

--------------------------------------------------------------------------------
INPUT CONTRACT (subset of the Normalized Tree used here)
--------------------------------------------------------------------------------
tree = {
  "language": "java",
  "units": [ {
      "id","name","owner_type","loc",
      "params":     [name, ...],
      "references": [data_id, ...],                # data the unit touches
      "globals":    [data_id, ...],                # optional: shared/global state
      "writes":     [data_id, ...],                # optional: mutated state
      "cfg": {"node_type","children":[...]},
      "meta": {                                    # all optional
          "static":       bool,                    # no seam for substitution
          "constructor_params": int,
          "nondeterministic": bool                 # clock / random / env / uuid
      }
  }, ... ],
  "call_graph":       {"edges":[{"from","to"}, ...]},
  "dependency_graph": {"edges":[{"from","to","kind":"db|external|platform|library|config|api"}, ...]}
}

CFG node types consumed:
    decision nodes (IF/FOR/WHILE/CASE/CATCH/AND/OR/...)  -> test burden
    IO, FILE, NETWORK, DB, SQL, PLATFORM                 -> friction (must be faked)

LANGUAGE NEUTRALITY
    Nothing here is language-specific. A COBOL paragraph reading WORKING-STORAGE,
    a PL/SQL package member reading a package global, and a Java method reading a
    static field are all "hidden input" and score identically.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Set

# Calibration on the per-unit testability score (burden + friction).
_BANDS = [(6, "L1"), (14, "L2"), (26, "L3"), (44, "L4")]  # else L5

_DECISION = {"IF", "ELIF", "FOR", "WHILE", "DO_WHILE", "CASE", "CASE_CLAUSE",
             "WHEN_CLAUSE", "CATCH", "EXCEPT", "TERNARY", "AND", "OR",
             "PERFORM_UNTIL", "UNTIL"}

# Nodes representing a real-world effect that a test must fake, contain, or
# tolerate. Each one is a reason a unit cannot simply be called with arguments.
_SIDE_EFFECT_NODES = {
    "IO": 3.0, "FILE": 3.0, "NETWORK": 4.0, "DB": 4.0, "SQL": 4.0,
    "EXEC_SQL": 4.0, "PLATFORM": 5.0, "SYSTEM": 5.0, "PRINT": 1.0,
    "DISPLAY": 1.0, "SCREEN": 3.0,
}

# Dependency kinds that must be stood up or stubbed before a test can run.
_HARD_DEPENDENCY_KINDS = {
    "db": 4.0, "platform": 5.0, "external": 3.0, "api": 3.0, "library": 1.0,
    "config": 2.0,
}


def _calibrate(score: float) -> str:
    for threshold, level in _BANDS:
        if score <= threshold:
            return level
    return "L5"


def _walk_cfg(cfg: Dict[str, Any]) -> Dict[str, int]:
    """Single pass: decision points and side-effect nodes by type."""
    counts: Dict[str, int] = defaultdict(int)
    if not cfg:
        return counts
    stack = [cfg]
    while stack:
        node = stack.pop()
        node_type = node.get("node_type")
        if node_type in _DECISION:
            counts["_decisions"] += 1
        if node_type in _SIDE_EFFECT_NODES:
            counts[node_type] += 1
        stack.extend(node.get("children", []) or [])
    return counts


def _score_unit(
    unit: Dict[str, Any],
    fan_out: Dict[str, Set[str]],
    dep_kinds_by_owner: Dict[str, Set[str]],
) -> Dict[str, Any]:
    unit_id = unit.get("id")
    cfg = unit.get("cfg") or {}
    counts = _walk_cfg(cfg)

    # ---- (a) TEST BURDEN -------------------------------------------------
    # Independent paths needing coverage. Linear and predictable: you can
    # estimate it, plan for it, and grind through it.
    cyclomatic = 1 + counts.get("_decisions", 0)
    burden = cyclomatic * 0.5

    # ---- (b) TEST FRICTION ----------------------------------------------
    # What stops the test being written at all. Weighted much harder than
    # burden, because 40 straightforward paths is a day's work while one
    # untestable hidden dependency can block the unit indefinitely.
    params = unit.get("params", []) or []
    references = set(unit.get("references", []) or [])
    globals_ = set(unit.get("globals", []) or [])
    writes = set(unit.get("writes", []) or [])
    meta = unit.get("meta", {}) or {}

    # Hidden inputs: state read but not passed in. The test must reproduce it
    # without any parameter to do so.
    hidden_inputs = globals_ or (references - set(params))
    f_hidden = len(hidden_inputs) * 2.0

    # Side effects on shared state: the test must assert on, and reset, state
    # the caller never handed over.
    shared_writes = writes & (globals_ or writes)
    f_effects = len(shared_writes) * 2.5

    # Environmental effects the test must fake.
    f_env = sum(
        _SIDE_EFFECT_NODES[k] * v for k, v in counts.items()
        if k in _SIDE_EFFECT_NODES
    )

    # Collaborators to stub.
    collaborators = fan_out.get(unit_id, set())
    f_collab = len(collaborators) * 1.5

    # Infrastructure that must exist for the unit to run at all.
    owner = unit.get("owner_type") or unit_id
    dep_kinds = dep_kinds_by_owner.get(owner, set())
    f_infra = sum(_HARD_DEPENDENCY_KINDS.get(k, 1.0) for k in dep_kinds)

    # Non-determinism: clock, random, uuid, environment. Without injection the
    # unit cannot have a stable assertion written against it at all.
    f_nondet = 6.0 if meta.get("nondeterministic") else 0.0

    # No seam: a static / non-substitutable unit cannot be isolated without
    # rewriting the caller or reaching for bytecode-level tooling.
    f_seam = 4.0 if meta.get("static") else 0.0

    # Setup burden before the unit can even be constructed.
    f_setup = float(meta.get("constructor_params", 0) or 0) * 1.0

    # Large parameter lists make every test case verbose and brittle.
    f_params = max(0, len(params) - 4) * 1.0

    friction = (f_hidden + f_effects + f_env + f_collab + f_infra
                + f_nondet + f_seam + f_setup + f_params)

    score = burden + friction

    blockers: List[str] = []
    if f_nondet:
        blockers.append("non-deterministic (clock/random/env) with no injection point")
    if f_seam:
        blockers.append("static / no substitution seam - cannot be isolated")
    if hidden_inputs:
        blockers.append(f"{len(hidden_inputs)} hidden input(s) not passed as parameters")
    if shared_writes:
        blockers.append(f"{len(shared_writes)} write(s) to shared state - test must reset it")
    if f_env:
        env_kinds = sorted(k for k in counts if k in _SIDE_EFFECT_NODES)
        blockers.append(f"environmental effects requiring fakes: {', '.join(env_kinds)}")
    if len(collaborators) >= 5:
        blockers.append(f"{len(collaborators)} collaborator(s) to stub")
    if dep_kinds & {"db", "platform"}:
        blockers.append(f"hard infrastructure dependency: {', '.join(sorted(dep_kinds & {'db', 'platform'}))}")

    # A unit can be simple to cover yet impossible to reach - that distinction
    # is the whole point of separating the two components.
    profile = (
        "blocked" if friction >= 20 and burden < 10 else
        "laborious" if burden >= 10 and friction < 10 else
        "hostile" if friction >= 20 and burden >= 10 else
        "tractable"
    )

    return {
        "unit": unit_id,
        "name": unit.get("name", unit_id),
        "owner_type": unit.get("owner_type"),
        "cyclomatic": cyclomatic,
        "min_test_cases": cyclomatic,
        "test_burden": round(burden, 1),
        "test_friction": round(friction, 1),
        "friction_breakdown": {
            "hidden_inputs": round(f_hidden, 1),
            "shared_state_writes": round(f_effects, 1),
            "environmental_effects": round(f_env, 1),
            "collaborators_to_stub": round(f_collab, 1),
            "infrastructure": round(f_infra, 1),
            "non_determinism": round(f_nondet, 1),
            "missing_seam": round(f_seam, 1),
            "setup_burden": round(f_setup, 1),
            "parameter_count": round(f_params, 1),
        },
        "profile": profile,
        "score": round(score, 1),
        "level": _calibrate(score),
        "blockers": blockers,
    }


def analyze(tree: Dict[str, Any]) -> Dict[str, Any]:
    units = tree.get("units", []) or []

    fan_out: Dict[str, Set[str]] = defaultdict(set)
    for edge in ((tree.get("call_graph") or {}).get("edges") or []):
        fan_out[edge.get("from")].add(edge.get("to"))

    dep_kinds_by_owner: Dict[str, Set[str]] = defaultdict(set)
    for edge in ((tree.get("dependency_graph") or {}).get("edges") or []):
        kind = (edge.get("kind") or "").lower()
        if kind:
            dep_kinds_by_owner[edge.get("from")].add(kind)

    items = [_score_unit(u, fan_out, dep_kinds_by_owner) for u in units]

    scores = [i["score"] for i in items]
    max_score = max(scores, default=0.0)
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    overall = _calibrate(max_score)

    untestable = [i for i in items if i["level"] in ("L4", "L5")]
    blocked = [i for i in items if i["profile"] in ("blocked", "hostile")]
    total_cases = sum(i["min_test_cases"] for i in items)

    return {
        "complexity": "Testability Complexity",
        "sno": 16,
        "language": tree.get("language", "unknown"),
        "derived_from": ["Cyclomatic Complexity", "Coupling", "Global State", "Side Effects"],
        "summary": {
            "level": overall,
            "score": round(max_score, 1),
            "headline": (
                f"{len(items)} unit(s); ~{total_cases} test case(s) for branch coverage; "
                f"{len(blocked)} unit(s) blocked or hostile to isolation"
            ),
        },
        "metrics": {
            "units": len(items),
            "min_test_cases_total": total_cases,
            "avg_test_burden": round(
                sum(i["test_burden"] for i in items) / len(items), 1) if items else 0.0,
            "avg_test_friction": round(
                sum(i["test_friction"] for i in items) / len(items), 1) if items else 0.0,
            "max_testability_score": round(max_score, 1),
            "avg_testability_score": avg_score,
            "hard_to_test_units": len(untestable),
            "profile_distribution": {
                p: len([i for i in items if i["profile"] == p])
                for p in ("tractable", "laborious", "blocked", "hostile")
            },
            "units_with_hidden_inputs": len(
                [i for i in items if i["friction_breakdown"]["hidden_inputs"] > 0]),
            "units_with_nondeterminism": len(
                [i for i in items if i["friction_breakdown"]["non_determinism"] > 0]),
        },
        "interpretation": {
            "tractable": "Callable in isolation; cover the paths and move on.",
            "laborious": "Many paths but few obstacles - predictable grind, safe to estimate.",
            "blocked": "Few paths but cannot be reached in isolation. Introduce a seam FIRST; "
                       "this is where characterization testing stalls.",
            "hostile": "Many paths AND heavy friction. Highest-risk units in the estate - "
                       "refactor for testability before attempting either tests or translation.",
        },
        "hotspots": sorted(untestable, key=lambda i: -i["score"])[:10],
        "items": items,
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
    id='testability_complexity',
    sno=16,
    name='Testability Complexity',
    tier='composite',
    requires=['units', 'cfg'],
    optional=['references', 'globals', 'writes', 'call_graph', 'dependency_graph', 'meta'],
    depends_on=[1, 4],
    summary='Test burden (paths) separated from test friction (obstacles).'
)

if __name__ == "__main__":
    raise SystemExit(_cli_main(analyze, SPEC))
