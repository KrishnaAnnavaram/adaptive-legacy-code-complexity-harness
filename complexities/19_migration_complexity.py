"""
Complexity #19 - Migration Complexity  (DERIVED)
================================================

What is it?      The effort and risk of moving this code to a different language,
                 runtime or platform - and which migration strategy it can
                 actually support.
Why needed?      This is the question a modernization programme is funded to
                 answer. Every other analyzer is an input to it. Migration effort
                 is NOT proportional to complexity: a 4,000-line unit of plain
                 nested IFs is tedious but mechanical, while a 200-line unit with
                 dynamic SQL and a platform call may be untranslatable by any
                 automated means. Blockers, not size, drive cost.
How it works?    Scores two things separately, because they behave differently:
                   VOLUME   - how much there is to move. Scales linearly, is
                              estimable, and automation reduces it.
                   BLOCKERS - what defeats automated translation entirely.
                              Does not scale with size, is not reduced by
                              automation, and drives the risk.
                 Then maps the result onto the standard migration strategies
                 (rehost / replatform / refactor / rearchitect / rebuild), since
                 the decision that matters is which strategy is viable, not what
                 the score is.
Input required   Normalized Tree, plus optionally the reports from the other
                 analyzers. Derived transparently - nothing invented.
Output artifact  Migration Complexity Report (returned as a dict).

--------------------------------------------------------------------------------
INPUT CONTRACT
--------------------------------------------------------------------------------
tree = {
  "language": "plsql",
  "target_language": "java",                     # optional, for portability notes
  "units": [ {
      "id","name","owner_type","loc",
      "cfg": {"node_type","children":[...]},
      "sql":  [ {"kind","dynamic":bool}, ... ],           # see #15
      "platform_calls": [ {"name","kind":"os|mq|screen|vendor|hardware"}, ... ],
      "dynamic_constructs": [ {"kind":"dynamic_sql|reflection|eval|alter|
                                       dynamic_dispatch|self_modifying"}, ... ],
      "conditional_compilation": [ {"flag":str}, ... ]    # see #18
  }, ... ],
  "dependency_graph": {"edges":[{"from","to","kind":"platform|external|library|db"}, ...]}
}

upstream = {                                     # ALL OPTIONAL
  "database":      <report from #15>,
  "testability":   <report from #16>,
  "runtime":       <report from #17>,
  "configuration": <report from #18>,
  "architectural": <report from #20>,
  "maintainability": <report from #11>,
}

When an upstream report is supplied its findings are used directly. When it is
absent the corresponding signal is derived from the tree where possible, and the
dimension is listed in `derivation.estimated` so the reader knows which parts of
the score rest on a full analysis and which on a fallback.

MIGRATION STRATEGY MAPPING (Gartner 5R family)
    rehost       lift and shift; code substantially unchanged
    replatform   same code, new runtime; limited targeted change
    refactor     restructure in place, keep the language
    rearchitect  significant redesign; decomposition required first
    rebuild      rewrite from requirements; translation is not viable
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

# Calibration on the per-unit migration score.
_BANDS = [(8, "L1"), (20, "L2"), (38, "L3"), (65, "L4")]  # else L5

# Blockers: constructs that defeat AUTOMATED translation. Weighted far above
# volume because they do not shrink with tooling and do not scale with size.
_BLOCKER_WEIGHT = {
    "self_modifying": 25.0,     # no static translation is correct
    "alter": 22.0,              # COBOL ALTER - rewrites a jump target at runtime
    "eval": 20.0,               # runtime-constructed code
    "reflection": 14.0,
    "dynamic_dispatch": 10.0,
    "dynamic_sql": 12.0,        # data lineage not statically resolvable
}

# Platform bindings: each needs a target-side equivalent that may not exist.
_PLATFORM_WEIGHT = {
    "hardware": 20.0,
    "os": 12.0,
    "screen": 10.0,             # terminal/3270 UI has no modern counterpart
    "mq": 8.0,
    "vendor": 8.0,
}

_UNSTRUCTURED = {"GOTO", "GO_TO", "ALTER", "PERFORM_THRU", "FALL_THROUGH",
                 "GOTO_DEPENDING"}

_DECISION = {"IF", "ELIF", "FOR", "WHILE", "DO_WHILE", "CASE", "CASE_CLAUSE",
             "WHEN_CLAUSE", "CATCH", "TERNARY", "AND", "OR", "PERFORM_UNTIL"}


def _calibrate(score: float) -> str:
    for threshold, level in _BANDS:
        if score <= threshold:
            return level
    return "L5"


def _level_rank(level: Optional[str]) -> int:
    return int(level[1]) if level and len(level) == 2 and level[0] == "L" else 0


def _walk(cfg: Dict[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    if not cfg:
        return counts
    stack = [cfg]
    while stack:
        node = stack.pop()
        node_type = node.get("node_type")
        if node_type in _DECISION:
            counts["decisions"] += 1
        if node_type in _UNSTRUCTURED:
            counts["unstructured"] += 1
        stack.extend(node.get("children", []) or [])
    return counts


def _upstream_unit_level(report: Optional[Dict[str, Any]], unit_id: str) -> Optional[str]:
    """Pull one unit's level out of an upstream report, if it has one."""
    if not report:
        return None
    for item in report.get("items", []) or []:
        if item.get("unit") == unit_id:
            return item.get("level")
    return None


def _strategy(volume: float, blockers: float, unstructured: int,
              in_cycle: bool) -> str:
    """Map the volume/blocker split onto a viable migration strategy.

    The split is the whole point. High volume with no blockers is a grind that
    automation handles - rehost or replatform. Low volume with hard blockers
    cannot be translated at any size - rebuild. Architectural entanglement
    forces rearchitecting regardless of either score, because a module inside a
    dependency cycle cannot be moved on its own.
    """
    if blockers >= 40:
        return "rebuild"
    if in_cycle and blockers >= 15:
        return "rearchitect"
    if blockers >= 20 or unstructured >= 8:
        return "rearchitect"
    if blockers >= 8 or unstructured >= 3:
        return "refactor"
    if volume >= 30:
        return "replatform"
    return "rehost"


def analyze(tree: Dict[str, Any],
            upstream: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    upstream = upstream or {}
    units = tree.get("units", []) or []

    db_report = upstream.get("database")
    test_report = upstream.get("testability")
    arch_report = upstream.get("architectural")
    config_report = upstream.get("configuration")
    runtime_report = upstream.get("runtime")

    # Modules trapped in a dependency cycle cannot be migrated independently.
    cyclic_modules: set = set()
    if arch_report:
        for cycle in arch_report.get("cycles", []) or []:
            cyclic_modules.update(cycle.get("modules", []) or [])

    platform_edges_by_module: Dict[str, int] = defaultdict(int)
    external_edges_by_module: Dict[str, int] = defaultdict(int)
    for edge in ((tree.get("dependency_graph") or {}).get("edges") or []):
        kind = (edge.get("kind") or "").lower()
        if kind == "platform":
            platform_edges_by_module[edge.get("from")] += 1
        elif kind in ("external", "library"):
            external_edges_by_module[edge.get("from")] += 1

    items: List[Dict[str, Any]] = []
    blocker_tally: Counter = Counter()

    for unit in units:
        unit_id = unit.get("id")
        module = unit.get("owner_type") or unit_id
        loc = int(unit.get("loc", 0) or 0)
        counts = _walk(unit.get("cfg") or {})

        # ---- VOLUME: scales linearly, automation reduces it ---------------
        v_size = loc / 50.0
        v_logic = counts.get("decisions", 0) * 0.25
        volume = v_size + v_logic

        # ---- BLOCKERS: defeat automation, do not scale with size ----------
        blockers = 0.0
        blocker_detail: List[str] = []

        for construct in unit.get("dynamic_constructs", []) or []:
            kind = (construct.get("kind") or "").lower()
            weight = _BLOCKER_WEIGHT.get(kind, 8.0)
            blockers += weight
            blocker_tally[kind] += 1
            blocker_detail.append(f"{kind} (+{weight:g})")

        dynamic_sql = len([s for s in (unit.get("sql") or []) if s.get("dynamic")])
        if dynamic_sql and not any(
            (c.get("kind") or "").lower() == "dynamic_sql"
            for c in (unit.get("dynamic_constructs") or [])
        ):
            weight = _BLOCKER_WEIGHT["dynamic_sql"] * min(dynamic_sql, 3) / 3
            blockers += weight
            blocker_tally["dynamic_sql"] += dynamic_sql
            blocker_detail.append(f"{dynamic_sql} dynamic SQL statement(s) (+{weight:.0f})")

        for call in unit.get("platform_calls", []) or []:
            kind = (call.get("kind") or "vendor").lower()
            weight = _PLATFORM_WEIGHT.get(kind, 8.0)
            blockers += weight
            blocker_tally[f"platform:{kind}"] += 1
            blocker_detail.append(f"platform {kind} call (+{weight:g})")

        unstructured = counts.get("unstructured", 0)
        if unstructured:
            weight = min(unstructured * 2.5, 25.0)
            blockers += weight
            blocker_tally["unstructured_flow"] += unstructured
            blocker_detail.append(f"{unstructured} unstructured jump(s) (+{weight:.0f})")

        cc_flags = len({c.get("flag") for c in (unit.get("conditional_compilation") or [])
                        if c.get("flag")})
        if cc_flags:
            weight = min(cc_flags * 3.0, 15.0)
            blockers += weight
            blocker_tally["build_variants"] += cc_flags
            blocker_detail.append(f"{cc_flags} compile flag(s) => multiple variants (+{weight:.0f})")

        n_platform = platform_edges_by_module.get(module, 0)
        if n_platform:
            weight = n_platform * 6.0
            blockers += weight
            blocker_detail.append(f"{n_platform} platform dependency/ies (+{weight:.0f})")

        n_external = external_edges_by_module.get(module, 0)
        blockers += n_external * 1.5

        # ---- upstream amplifiers -----------------------------------------
        # Database coupling and untestability do not block translation, but
        # they raise the risk of a translation nobody can verify.
        amplifiers: List[str] = []
        db_level = _upstream_unit_level(db_report, unit_id)
        if _level_rank(db_level) >= 4:
            blockers += 6.0
            amplifiers.append(f"database complexity {db_level}")

        test_level = _upstream_unit_level(test_report, unit_id)
        if _level_rank(test_level) >= 4:
            blockers += 8.0
            amplifiers.append(f"testability {test_level} - migration cannot be verified")

        rt_level = _upstream_unit_level(runtime_report, unit_id)
        if _level_rank(rt_level) >= 4:
            volume += 4.0
            amplifiers.append(f"runtime complexity {rt_level} - performance re-validation needed")

        in_cycle = module in cyclic_modules
        if in_cycle:
            blockers += 10.0
            amplifiers.append(f"module '{module}' is inside a dependency cycle - cannot move alone")

        score = volume + blockers
        strategy = _strategy(volume, blockers, unstructured, in_cycle)

        # Automatability: the share of the work a tool can plausibly do.
        automatable = volume / score if score > 0 else 1.0

        items.append({
            "unit": unit_id,
            "name": unit.get("name", unit_id),
            "owner_type": module,
            "loc": loc,
            "volume_score": round(volume, 1),
            "blocker_score": round(blockers, 1),
            "score": round(score, 1),
            "level": _calibrate(score),
            "automatable_fraction": round(automatable, 2),
            "recommended_strategy": strategy,
            "unstructured_jumps": unstructured,
            "dynamic_sql": dynamic_sql,
            "platform_calls": len(unit.get("platform_calls", []) or []),
            "in_dependency_cycle": in_cycle,
            "blockers": blocker_detail,
            "amplifiers": amplifiers,
        })

    scores = [i["score"] for i in items]
    max_score = max(scores, default=0.0)
    total_volume = sum(i["volume_score"] for i in items)
    total_blockers = sum(i["blocker_score"] for i in items)
    overall = _calibrate(max_score)

    strategy_dist: Counter = Counter(i["recommended_strategy"] for i in items)
    blocked = [i for i in items if i["recommended_strategy"] in ("rebuild", "rearchitect")]

    portfolio_automatable = (
        total_volume / (total_volume + total_blockers)
        if (total_volume + total_blockers) > 0 else 1.0
    )

    supplied = [k for k in ("database", "testability", "runtime", "configuration",
                            "architectural", "maintainability") if upstream.get(k)]
    estimated = [k for k in ("database", "testability", "runtime", "configuration",
                             "architectural") if not upstream.get(k)]

    caveats: List[str] = []
    if estimated:
        caveats.append(
            "Upstream report(s) not supplied: " + ", ".join(estimated) +
            ". Their contribution was estimated from the tree where possible and "
            "omitted where not. Re-run with the full set for a costing-grade figure."
        )
    if config_report:
        variants = (config_report.get("metrics") or {}).get("estimated_build_variants", 1)
        if variants > 1:
            caveats.append(
                f"Configuration analysis reports up to {variants} build variant(s). "
                f"This migration assessment describes ONE of them."
            )

    return {
        "complexity": "Migration Complexity",
        "sno": 19,
        "language": tree.get("language", "unknown"),
        "target_language": tree.get("target_language"),
        "derived_from": ["LOC", "Cyclomatic Complexity", "Database Complexity",
                         "Testability Complexity", "Runtime Complexity",
                         "Configuration Complexity", "Architectural Complexity"],
        "derivation": {"supplied": supplied, "estimated": estimated},
        "summary": {
            "level": overall,
            "score": round(max_score, 1),
            "headline": (
                f"{len(items)} unit(s); {len(blocked)} require rearchitecture or rebuild; "
                f"~{round(portfolio_automatable * 100)}% of the work is plausibly automatable; "
                f"{sum(blocker_tally.values())} translation blocker(s) found"
            ),
        },
        "metrics": {
            "units": len(items),
            "total_loc": sum(i["loc"] for i in items),
            "total_volume_score": round(total_volume, 1),
            "total_blocker_score": round(total_blockers, 1),
            "portfolio_automatable_fraction": round(portfolio_automatable, 2),
            "max_migration_score": round(max_score, 1),
            "avg_migration_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "units_requiring_rebuild": strategy_dist.get("rebuild", 0),
            "units_requiring_rearchitect": strategy_dist.get("rearchitect", 0),
            "units_requiring_refactor": strategy_dist.get("refactor", 0),
            "units_replatformable": strategy_dist.get("replatform", 0),
            "units_rehostable": strategy_dist.get("rehost", 0),
            "blocker_breakdown": dict(blocker_tally),
        },
        "strategy_distribution": dict(strategy_dist),
        "interpretation": {
            "volume_vs_blockers": (
                "Volume scales with size and shrinks with tooling. Blockers do neither. "
                "A high-volume, low-blocker estate is a predictable grind that automation "
                "makes cheap. A low-volume, high-blocker estate is small, looks cheap, "
                "and is where migration programmes overrun."
            ),
            "rehost": "Move as-is. No structural obstacle found.",
            "replatform": "Large but mechanical. Targeted runtime changes only.",
            "refactor": "Restructure in place before moving; keep the language.",
            "rearchitect": "Decompose first - dependency cycles or unstructured flow "
                           "prevent the unit being moved on its own.",
            "rebuild": "Translation is not viable. Rebuild from requirements and use "
                       "the existing code as the specification.",
        },
        "caveats": caveats,
        "hotspots": sorted(items, key=lambda i: -i["blocker_score"])[:10],
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
    id='migration_complexity',
    sno=19,
    name='Migration Complexity',
    tier='composite',
    requires=['units', 'cfg'],
    optional=['sql', 'platform_calls', 'dynamic_constructs', 'dependency_graph', 'conditional_compilation', 'loc'],
    depends_on=[3, 15, 16, 17, 20],
    summary='Volume vs blockers, mapped onto a migration strategy per unit.'
)

if __name__ == "__main__":
    raise SystemExit(_cli_main(analyze, SPEC))
