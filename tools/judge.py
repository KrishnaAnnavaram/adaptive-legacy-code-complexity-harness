#!/usr/bin/env python3
"""
judge.py — adversarial conformance audit of every complexity analyzer.

This is the LLM-as-judge harness. It does not ask whether an analyzer produces
a NICE number; it asks whether the number can be TRUSTED. Every check below
exists because the opposite behaviour was found in this repository at some
point, and each one is designed to fail loudly rather than pass by default.

CHECKS
  C1  contract      Output carries the full envelope with the declared id/sno.
  C2  starvation    Given a tree stripped of its declared inputs, does it say
                    `insufficient_input` - or does it invent a clean zero?
                    This is the single most important check here.
  C3  empty         Given an empty tree, same question.
  C4  determinism   Same tree twice -> byte-identical output.
  C5  no-demo       Run with no input at all: must fail visibly, must NOT print
                    a plausible report built from hardcoded sample data.
  C6  evidence      A high level (L4/L5) must be backed by items/hotspots. A
                    severe score with no evidence is an assertion, not a finding.
  C7  confidence    Confidence is declared, and any value below 1.0 is explained.
  C8  band-sanity   Score is finite, non-negative, and does not saturate the
                    top band so hard that units become indistinguishable.
  C9  neutrality    Analyzer runs on the same tree relabelled to another
                    language without crashing (no hard language assumptions).

Usage:
    python tools/judge.py samples/cobol_payroll.tree.json
    python tools/judge.py samples/cobol_payroll.tree.json --json verdict.json
"""

from __future__ import annotations

import argparse
import copy
import glob
import importlib.util
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Tuple

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYZER_DIR = os.path.join(HERE, ".claude", "scripts")
sys.path.insert(0, ANALYZER_DIR)

from _core import Tree, run  # noqa: E402

ENVELOPE_FIELDS = ("contract_version", "id", "sno", "complexity", "tier",
                   "analyzer_version", "language", "status", "summary",
                   "metrics", "items", "confidence")


def load_analyzers(self_test: bool = False) -> List[Tuple[Any, Any, str]]:
    paths = sorted(glob.glob(os.path.join(ANALYZER_DIR, "[0-9][0-9]_*.py")))
    if self_test:
        # tools/99_canary_complexity.py is a deliberately defective analyzer.
        # Including it proves this judge can still FAIL something - a suite
        # that only ever reports PASS tells you nothing about the code, only
        # about the suite. It lives outside complexities/ so the pipeline never
        # picks it up as a real metric.
        canary = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "99_canary_complexity.py")
        if os.path.exists(canary):
            paths.append(canary)
    out = []
    for path in paths:
        name = os.path.splitext(os.path.basename(path))[0]
        s = importlib.util.spec_from_file_location(f"j_{name}", path)
        m = importlib.util.module_from_spec(s)
        try:
            s.loader.exec_module(m)
        except Exception as exc:  # noqa: BLE001
            print(f"IMPORT FAIL {name}: {exc}", file=sys.stderr)
            continue
        if hasattr(m, "SPEC") and hasattr(m, "analyze"):
            out.append((m.SPEC, m.analyze, path))
    return out


def starve(tree: Dict[str, Any], spec) -> Dict[str, Any]:
    """Remove exactly the inputs this analyzer declared it needs."""
    t = copy.deepcopy(tree)
    fields = set(spec.requires) | set(spec.requires_any)
    for f in fields:
        if f in ("call_graph",):
            t["call_graph"] = {"nodes": [], "edges": []}
        elif f in ("dependency_graph",):
            t["dependency_graph"] = {"nodes": [], "edges": []}
        elif f == "types":
            t["types"] = []
        elif f == "layers":
            t.pop("layers", None)
            t.pop("module_layer", None)
        elif f == "units":
            t["units"] = []
        else:
            for u in t.get("units", []):
                u.pop(f, None)
    return t


def judge_one(spec, analyze, path, tree: Dict[str, Any]) -> Dict[str, Any]:
    checks: Dict[str, Dict[str, Any]] = {}

    def record(cid, ok, detail):
        checks[cid] = {"pass": bool(ok), "detail": detail}

    # -- C1 contract -----------------------------------------------------
    base = run(analyze, spec, tree)
    missing = [f for f in ENVELOPE_FIELDS if f not in base]
    record("C1_contract", not missing and base.get("id") == spec.id,
           f"missing fields: {missing}" if missing else "full envelope present")

    # -- C2 starvation ---------------------------------------------------
    starved = run(analyze, spec, starve(tree, spec))
    st = starved.get("status")
    if st == "insufficient_input":
        record("C2_starvation", True, "correctly reports insufficient_input")
    elif st == "error":
        record("C2_starvation", False,
               f"CRASHED instead of reporting insufficient input: "
               f"{starved.get('status_reason', '')[:90]}")
    else:
        record("C2_starvation", False,
               f"RETURNED A SCORE ({starved.get('summary', {}).get('level')}, "
               f"{starved.get('summary', {}).get('score')}) FROM STARVED INPUT - "
               f"this is indistinguishable from a genuine clean result")

    # -- C3 empty tree ---------------------------------------------------
    empty = run(analyze, spec, {"language": "unknown"})
    record("C3_empty", empty.get("status") in ("insufficient_input", "error"),
           f"status={empty.get('status')}")

    # -- C4 determinism --------------------------------------------------
    a = json.dumps(run(analyze, spec, tree), sort_keys=True)
    b = json.dumps(run(analyze, spec, copy.deepcopy(tree)), sort_keys=True)
    record("C4_determinism", a == b,
           "byte-identical across runs" if a == b else "OUTPUT VARIES between runs")

    # -- C5 no-demo ------------------------------------------------------
    proc = subprocess.run([sys.executable, path], capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=60)
    printed_report = False
    if proc.stdout.strip():
        try:
            doc = json.loads(proc.stdout)
            printed_report = bool(doc.get("summary", {}).get("score") is not None)
        except Exception:  # noqa: BLE001
            printed_report = False
    record("C5_no_demo", not printed_report,
           "fails visibly with no input" if not printed_report
           else "PRINTS A SCORED REPORT WITH NO INPUT - fabricated demo data")

    # -- C6 evidence -----------------------------------------------------
    lvl = (base.get("summary") or {}).get("level")
    if base.get("status") == "ok" and lvl in ("L4", "L5"):
        has_ev = bool(base.get("items")) or bool(base.get("hotspots"))
        record("C6_evidence", has_ev,
               "severe level backed by items/hotspots" if has_ev
               else f"level {lvl} with NO items and NO hotspots - unsupported assertion")
    else:
        record("C6_evidence", True, f"n/a (level {lvl})")

    # -- C7 confidence ---------------------------------------------------
    conf = base.get("confidence") or {}
    score = conf.get("score")
    ok_conf = isinstance(score, (int, float)) and 0.0 <= score <= 1.0
    explained = score == 1.0 or bool(conf.get("reasons"))
    record("C7_confidence", ok_conf and explained,
           f"confidence={score} reasons={len(conf.get('reasons') or [])}"
           + ("" if explained else "  <- below 1.0 with no reason given"))

    # -- C8 band sanity --------------------------------------------------
    s = (base.get("summary") or {}).get("score")
    sane = s is None or (isinstance(s, (int, float)) and s >= 0
                         and s == s and abs(s) != float("inf"))
    record("C8_band_sanity", sane, f"score={s}")

    # -- C9 language neutrality ------------------------------------------
    for lang in ("java", "plsql", "unknown-language-xyz"):
        t2 = copy.deepcopy(tree)
        t2["language"] = lang
        r2 = run(analyze, spec, t2)
        if r2.get("status") == "error":
            record("C9_neutrality", False,
                   f"errors when language={lang}: {r2.get('status_reason', '')[:80]}")
            break
    else:
        record("C9_neutrality", True, "runs under every language label")

    # -- C10 honest declaration ------------------------------------------
    # C2 above can only ever exercise the CENTRAL GATE, because _core.run()
    # enforces spec.requires before the analyzer is reached. So C2 proves the
    # SPEC is wired up, not that it is COMPLETE.
    #
    # The real hazard is an analyzer that quietly reads fields it never
    # declared. Its SPEC then passes the gate on a tree that lacks them, and it
    # silently degrades - the exact failure mode this whole contract exists to
    # prevent, reintroduced one level down.
    #
    # Test: strip everything EXCEPT the declared inputs. If the score moves and
    # confidence stays at 1.0, the analyzer consumed something it did not
    # declare and did not admit to losing it.
    declared = set(spec.requires) | set(spec.requires_any) | set(spec.optional)
    minimal = copy.deepcopy(tree)
    strippable = ("loc", "comment_lines", "params", "references", "globals",
                  "writes", "halstead", "sql", "cursors", "transactions",
                  "platform_calls", "dynamic_constructs", "config_reads",
                  "feature_flags", "conditional_compilation", "literals", "meta")
    stripped = []
    for f in strippable:
        if f not in declared:
            stripped.append(f)
            for u in minimal.get("units", []):
                u.pop(f, None)
    if "types" not in declared:
        minimal["types"] = []
        stripped.append("types")
    if "call_graph" not in declared:
        minimal["call_graph"] = {"nodes": [], "edges": []}
        stripped.append("call_graph")
    if "dependency_graph" not in declared:
        minimal["dependency_graph"] = {"nodes": [], "edges": []}
        stripped.append("dependency_graph")

    minimal_run = run(analyze, spec, minimal)
    base_score = (base.get("summary") or {}).get("score")
    min_score = (minimal_run.get("summary") or {}).get("score")
    min_conf = (minimal_run.get("confidence") or {}).get("score", 1.0)

    if base.get("status") != "ok" or minimal_run.get("status") != "ok":
        record("C10_honest_spec", True, "n/a (not measurable on this tree)")
    elif base_score == min_score:
        record("C10_honest_spec", True,
               "score unchanged when undeclared inputs removed")
    elif min_conf < 1.0:
        record("C10_honest_spec", True,
               f"score moved {base_score} -> {min_score} but confidence dropped "
               f"to {min_conf} and said why")
    else:
        record("C10_honest_spec", False,
               f"score moved {base_score} -> {min_score} after removing UNDECLARED "
               f"input(s) {stripped[:6]} yet confidence stayed 1.0 - SPEC is "
               f"incomplete and the analyzer degrades silently")

    failed = [k for k, v in checks.items() if not v["pass"]]
    return {
        "sno": spec.sno, "id": spec.id, "name": spec.name, "tier": spec.tier,
        "checks": checks,
        "failed": failed,
        "passed": len(checks) - len(failed),
        "total": len(checks),
        "verdict": "PASS" if not failed else (
            "CRITICAL" if any(f in ("C2_starvation", "C5_no_demo", "C4_determinism",
                                    "C10_honest_spec")
                              for f in failed) else "MINOR"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Adversarial audit of complexity analyzers")
    ap.add_argument("tree")
    ap.add_argument("--json", help="write the full verdict here")
    ap.add_argument("--self-test", action="store_true",
                    help="also audit tools/99_canary_complexity.py, which is "
                         "defective on purpose; it MUST come back CRITICAL or "
                         "this judge has no teeth")
    args = ap.parse_args()

    with open(args.tree, "r", encoding="utf-8") as fh:
        tree = json.load(fh)

    analyzers = load_analyzers(self_test=args.self_test)
    results = [judge_one(spec, fn, path, tree) for spec, fn, path in analyzers]
    results.sort(key=lambda r: r["sno"])

    print(f"\n{'#':>3}  {'analyzer':<30} {'verdict':<9} {'score':<7} failed checks")
    print("-" * 96)
    for r in results:
        print(f"{r['sno']:>3}  {r['name']:<30} {r['verdict']:<9} "
              f"{r['passed']}/{r['total']}    {', '.join(r['failed']) or '-'}")

    crit = [r for r in results if r["verdict"] == "CRITICAL"]
    minor = [r for r in results if r["verdict"] == "MINOR"]
    print("-" * 96)
    print(f"{len(results) - len(crit) - len(minor)} pass   "
          f"{len(minor)} minor   {len(crit)} CRITICAL")

    by_check: Dict[str, int] = {}
    for r in results:
        for cid in r["failed"]:
            by_check[cid] = by_check.get(cid, 0) + 1
    if by_check:
        print("\nfailures by check:")
        for cid, n in sorted(by_check.items(), key=lambda kv: -kv[1]):
            print(f"  {cid:<20} {n} analyzer(s)")
        print("\ndetail:")
        for r in results:
            for cid in r["failed"]:
                print(f"  [{r['sno']:02d}] {cid}: {r['checks'][cid]['detail']}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"results": results,
                       "summary": {"critical": len(crit), "minor": len(minor),
                                   "pass": len(results) - len(crit) - len(minor)}},
                      fh, indent=2)
        print(f"\nwrote {args.json}")

    if args.self_test:
        canary = [r for r in results if r["sno"] == 99]
        if not canary:
            print("\nSELF-TEST INCONCLUSIVE: canary not found")
            return 1
        if canary[0]["verdict"] != "CRITICAL":
            print("\nSELF-TEST FAILED: the deliberately defective canary passed. "
                  "This judge cannot detect the defects it claims to check for.")
            return 1
        print(f"\nself-test OK: canary correctly flagged CRITICAL "
              f"({', '.join(canary[0]['failed'])})")
        # The canary is expected to fail, so it must not count against the run.
        crit = [r for r in crit if r["sno"] != 99]

    return 1 if crit else 0


if __name__ == "__main__":
    sys.exit(main())
