#!/usr/bin/env python3
"""
run_pipeline.py — run every complexity analyzer over one Normalized Tree.

Discovers analyzers by scanning complexities/NN_*.py and reading each module's
SPEC. There is no hardcoded list anywhere: adding an analyzer means dropping in
a file, and it joins the next run automatically.

Ordering is derived, not configured:
    tier band      size -> structural -> data -> coupling -> hazard -> composite
    then           dependency level (from SPEC.depends_on)
    then           sno, so two runs over the same tree produce the same order

Composite analyzers receive the reports of the analyzers they declared as
depends_on, so #19 Migration is scored from real upstream findings rather than
from re-derived approximations.

Usage:
    python run_pipeline.py TREE.json
    python run_pipeline.py TREE.json -o out/
    python run_pipeline.py TREE.json --only 1,3,17
    python run_pipeline.py --list
"""

from __future__ import annotations

import argparse
import datetime
import glob
import importlib.util
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
#: Analyzers live beside this file in .claude/scripts/, mirroring the
#: plsql_to_brd layout where every executable step sits under .claude/scripts.
ANALYZER_DIR = HERE
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ANALYZER_DIR)

from _core import TIERS, Tree, run  # noqa: E402

PIPELINE_VERSION = "1.0.0"

#: Which upstream report each composite wants, keyed by the sno it depends on.
_UPSTREAM_KEYS = {
    15: "database", 16: "testability", 17: "runtime",
    18: "configuration", 20: "architectural", 11: "maintainability",
}


def discover() -> List[Tuple[Any, Any]]:
    """Import every NN_*.py that exports both SPEC and analyze."""
    found = []
    for path in sorted(glob.glob(os.path.join(ANALYZER_DIR, "[0-9][0-9]_*.py"))):
        name = os.path.splitext(os.path.basename(path))[0]
        spec_obj = importlib.util.spec_from_file_location(f"cx_{name}", path)
        module = importlib.util.module_from_spec(spec_obj)
        try:
            spec_obj.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {name}: failed to import — {type(exc).__name__}: {exc}",
                  file=sys.stderr)
            continue
        if not hasattr(module, "SPEC") or not hasattr(module, "analyze"):
            print(f"  ! {name}: no SPEC or analyze(); skipped", file=sys.stderr)
            continue
        found.append((module.SPEC, module.analyze))
    return found


def order(analyzers: List[Tuple[Any, Any]]) -> List[Tuple[Any, Any]]:
    """Tier band, then dependency depth, then sno. Fully deterministic."""
    by_sno = {spec.sno: spec for spec, _ in analyzers}

    def depth(sno: int, seen: Optional[set] = None) -> int:
        seen = seen or set()
        if sno in seen:
            return 0                       # cycle guard; reported separately
        spec = by_sno.get(sno)
        if not spec or not spec.depends_on:
            return 0
        return 1 + max((depth(d, seen | {sno}) for d in spec.depends_on
                        if d in by_sno), default=-1)

    return sorted(
        analyzers,
        key=lambda pair: (TIERS.index(pair[0].tier), depth(pair[0].sno), pair[0].sno),
    )


def execute(tree_raw: Dict[str, Any],
            analyzers: List[Tuple[Any, Any]]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    by_sno: Dict[int, Dict[str, Any]] = {}

    for spec, analyze in analyzers:
        upstream = {
            _UPSTREAM_KEYS[d]: by_sno[d]
            for d in spec.depends_on
            if d in by_sno and d in _UPSTREAM_KEYS
            and by_sno[d].get("status") == "ok"
        }

        if upstream:
            # Composites that accept upstream take a second argument. Anything
            # that does not simply runs on the tree alone.
            def call(t, _fn=analyze, _up=upstream):
                try:
                    return _fn(t, _up)
                except TypeError:
                    return _fn(t)
            out = run(call, spec, tree_raw)
            out["upstream_used"] = sorted(upstream)
        else:
            out = run(analyze, spec, tree_raw)

        by_sno[spec.sno] = out
        results.append(out)

        status = out.get("status")
        mark = {"ok": "OK  ", "insufficient_input": "SKIP", "error": "FAIL"}.get(status, "??  ")
        summary = out.get("summary") or {}
        detail = (f"{summary.get('level') or '--'}  score={summary.get('score')}"
                  if status == "ok" else out.get("status_reason", "")[:70])
        print(f"  {mark} {spec.sno:02d} {spec.name:<32} {detail}", file=sys.stderr)

    return results


def consolidate(tree_raw: Dict[str, Any], results: List[Dict[str, Any]],
                tree_path: Optional[str]) -> Dict[str, Any]:
    tree = Tree(tree_raw)
    ok = [r for r in results if r.get("status") == "ok"]
    skipped = [r for r in results if r.get("status") == "insufficient_input"]
    failed = [r for r in results if r.get("status") == "error"]

    levels = [r["summary"]["level"] for r in ok if r["summary"].get("level")]
    ranks = [int(l[1]) for l in levels if isinstance(l, str) and len(l) == 2]

    # Per-unit rollup across every analyzer that reported at unit granularity.
    per_unit: Dict[str, Dict[str, Any]] = {}
    for r in ok:
        for item in r.get("items") or []:
            uid = item.get("unit")
            if not uid:
                continue
            row = per_unit.setdefault(uid, {"unit": uid, "name": item.get("name", uid),
                                            "levels": {}, "flagged_by": []})
            lvl = item.get("level")
            if lvl:
                row["levels"][r["id"]] = lvl
                if lvl in ("L4", "L5"):
                    row["flagged_by"].append(r["id"])

    for row in per_unit.values():
        row["corroboration"] = len(row["flagged_by"])
        row["worst_level"] = (f"L{max(int(l[1]) for l in row['levels'].values())}"
                              if row["levels"] else None)

    # Corroboration filter: a unit flagged by one analyzer is usually that
    # analyzer's bias. Two or more independent analyzers agreeing is a finding.
    hotspots = sorted(
        [r for r in per_unit.values() if r["corroboration"] >= 2],
        key=lambda r: (-r["corroboration"], r["unit"]),
    )

    return {
        "artifact_version": "1.0",
        "pipeline_version": PIPELINE_VERSION,
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
                        .replace(microsecond=0).isoformat(),
        "tree": {
            "path": tree_path,
            "language": tree.language,
            "source_file": tree.source_file,
            "units": len(tree.units),
            "capabilities": tree.capabilities(),
        },
        "coverage": {
            "analyzers_discovered": len(results),
            "analyzers_ok": len(ok),
            "analyzers_insufficient_input": len(skipped),
            "analyzers_error": len(failed),
            "completeness": round(len(ok) / len(results), 3) if results else 0.0,
            "not_measured": [
                {"sno": r["sno"], "id": r["id"], "reason": r.get("status_reason")}
                for r in skipped + failed
            ],
        },
        "overall": {
            "level": f"L{max(ranks)}" if ranks else None,
            "mean_level": round(sum(ranks) / len(ranks), 2) if ranks else None,
            "mean_confidence": round(
                sum((r.get("confidence") or {}).get("score", 1.0) for r in ok) / len(ok), 2
            ) if ok else None,
        },
        "by_tier": {
            tier: [
                {"sno": r["sno"], "id": r["id"],
                 "level": r["summary"].get("level"),
                 "score": r["summary"].get("score"),
                 "status": r["status"]}
                for r in results if r.get("tier") == tier
            ]
            for tier in TIERS
        },
        "hotspots": hotspots[:25],
        "reports": [
            {"sno": r["sno"], "id": r["id"], "status": r["status"],
             "level": r["summary"].get("level"), "score": r["summary"].get("score"),
             "headline": r["summary"].get("headline"),
             "confidence": (r.get("confidence") or {}).get("score")}
            for r in results
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Run all complexity analyzers over one tree")
    ap.add_argument("tree", nargs="?", help="Normalized Tree JSON")
    ap.add_argument("-o", "--output-dir", default="out")
    ap.add_argument("--only", help="comma-separated sno list, e.g. 1,3,17")
    ap.add_argument("--list", action="store_true", help="list discovered analyzers and exit")
    args = ap.parse_args()

    print("Discovering analyzers...", file=sys.stderr)
    analyzers = order(discover())
    print(f"  {len(analyzers)} analyzer(s) found\n", file=sys.stderr)

    if args.list:
        for spec, _ in analyzers:
            need = ", ".join(spec.requires) or "-"
            any_ = f" | any of: {', '.join(spec.requires_any)}" if spec.requires_any else ""
            print(f"  {spec.sno:02d}  {spec.name:<32} tier={spec.tier:<11} "
                  f"requires: {need}{any_}")
        return 0

    if not args.tree:
        ap.error("a tree file is required (or use --list)")

    if args.only:
        keep = {int(x) for x in args.only.split(",")}
        analyzers = [a for a in analyzers if a[0].sno in keep]

    with open(args.tree, "r", encoding="utf-8") as fh:
        tree_raw = json.load(fh)

    print(f"Running {len(analyzers)} analyzer(s) on {args.tree}", file=sys.stderr)
    results = execute(tree_raw, analyzers)

    artifact = consolidate(tree_raw, results, args.tree)

    outdir = args.output_dir
    os.makedirs(os.path.join(outdir, "reports"), exist_ok=True)
    for r in results:
        with open(os.path.join(outdir, "reports", f"{r['sno']:02d}_{r['id']}.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(r, fh, indent=2)
    with open(os.path.join(outdir, "complexity_artifact.json"), "w", encoding="utf-8") as fh:
        json.dump(artifact, fh, indent=2)

    cov = artifact["coverage"]
    print(f"\n  measured {cov['analyzers_ok']}/{cov['analyzers_discovered']} "
          f"({round(cov['completeness'] * 100)}%)   "
          f"not measured: {cov['analyzers_insufficient_input']}   "
          f"errors: {cov['analyzers_error']}", file=sys.stderr)
    print(f"  overall level {artifact['overall']['level']}   "
          f"hotspots {len(artifact['hotspots'])}", file=sys.stderr)
    print(f"  -> {outdir}/complexity_artifact.json", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
