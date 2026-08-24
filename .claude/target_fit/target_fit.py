"""
Target-Fit Analyzer (Agent 4)
==============================
What is it?      A target-language counterpart to Agent 3. Takes a Normalized
                 Tree (Agent 2's output) and one target language, projects
                 the tree onto that target using generic, declared mapping
                 rules (see project_tree.py), then runs the SAME 20
                 complexity analyzers Agent 3 uses - unmodified, unduplicated
                 - against the projected tree. The result is a real,
                 independently-computed target-side complexity artifact,
                 structurally identical to Agent 3's own
                 complexity_artifact.json.
Why needed?      A source-language score is not automatically a
                 target-language score. Some metrics genuinely don't change
                 (cyclomatic complexity counts decision points, which
                 survive a faithful translation); some genuinely can't be
                 known without real target code (LOC-driven metrics); and
                 some depend on whether the target can even express what the
                 source does (GOTO/ALTER). The only way to get real numbers
                 instead of guesses for all 20 is to actually run the real
                 analyzers against a tree that honestly represents what
                 survives projection - not to copy or reweight numbers
                 Agent 3 already produced for the SOURCE language.
How it works?    1. Load the Normalized Tree and one target descriptor.
                 2. project_tree() rewrites it: units with an unexpressible
                    jump construct are dropped (never invented-restructured);
                    `types` is dropped if the target has no object model;
                    LOC/comment/Halstead fields are stripped everywhere,
                    always - no verbosity ratio is ever invented.
                 3. .claude/complexities/run_pipeline.py's own discover(),
                    order(), execute() and consolidate() - the exact same
                    functions Agent 3's pipeline uses - run against the
                    PROJECTED tree. Every one of the 20 analyzers gates on
                    its own declared `requires`/`optional` exactly as it
                    already does for any tree; a metric this projection
                    starved of what it needs reports insufficient_input,
                    same as it always would.
                 4. Agent 3's own complexity_artifact.json, if present next
                    to the source tree, is read ONLY to build a `comparison`
                    section pairing source vs. target results side by side -
                    it is never consulted to produce a target score.
Input required   NORMALIZED_TREE.json (Agent 2's output) and a target
                 language id with a descriptor under languages/.

Standalone script, standard library only. Imports run_pipeline.py and the 20
analyzers directly (already-existing, already-audited code) rather than
duplicating any of their logic - see docs/target-fit-contract.md.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMPLEXITIES_DIR = os.path.join(os.path.dirname(HERE), "complexities")
sys.path.insert(0, COMPLEXITIES_DIR)
sys.path.insert(0, HERE)

import run_pipeline  # noqa: E402  (the real Agent 3 pipeline module, reused)
from project_tree import project_tree  # noqa: E402


def _load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def find_descriptor(languages_dir, target):
    path = os.path.join(languages_dir, f"{target}.json")
    if not os.path.isfile(path):
        available = []
        if os.path.isdir(languages_dir):
            available = sorted(
                fn[:-5] for fn in os.listdir(languages_dir) if fn.endswith(".json")
            )
        raise SystemExit(
            "insufficient_input: no capability descriptor for target "
            f"'{target}'.\n"
            f"Available targets: {', '.join(available) if available else '(none)'}\n"
            f"To add one, see {os.path.join(os.path.dirname(languages_dir), 'schema.md')}"
        )
    return _load_json(path)


def build_comparison(target_reports, source_artifact):
    """Pairs Agent 3's real source-side results with this run's real
    target-side results, sno by sno - traceability only, never the mechanism
    that produced the target numbers."""
    source_by_sno = {r["sno"]: r for r in (source_artifact or {}).get("reports", [])}
    comparison = []
    for r in target_reports:
        src = source_by_sno.get(r["sno"], {})
        comparison.append({
            "sno": r["sno"],
            "id": r["id"],
            "source_status": src.get("status"),
            "source_score": src.get("score"),
            "source_level": src.get("level"),
            "target_status": r["status"],
            "target_score": r["score"],
            "target_level": r["level"],
        })
    return comparison


def analyze(tree_path, target, languages_dir, source_artifact_path=None):
    source_tree_raw = _load_json(tree_path)
    descriptor = find_descriptor(languages_dir, target)
    reviewed = bool(descriptor.get("reviewed", False))

    projected_tree_raw, projection_log = project_tree(source_tree_raw, descriptor)

    analyzers = run_pipeline.order(run_pipeline.discover())
    results = run_pipeline.execute(projected_tree_raw, analyzers)
    artifact = run_pipeline.consolidate(projected_tree_raw, results, tree_path)

    source_artifact = None
    if source_artifact_path is None:
        candidate = os.path.join(os.path.dirname(os.path.abspath(tree_path)), "complexity_artifact.json")
        if os.path.isfile(candidate):
            source_artifact_path = candidate
    if source_artifact_path and os.path.isfile(source_artifact_path):
        source_artifact = _load_json(source_artifact_path)

    comparison = build_comparison(artifact["reports"], source_artifact)

    artifact["source_language"] = source_tree_raw.get("language", "unknown")
    artifact["target_language"] = target
    artifact["descriptor_source"] = descriptor.get("source", "unknown")
    artifact["descriptor_reviewed"] = reviewed
    artifact["confidence"] = {
        "score": 1.0 if reviewed else 0.6,
        "reasons": (
            []
            if reviewed
            else [
                f"target descriptor for '{target}' has not been human-reviewed yet "
                "(see .claude/target_fit/languages/_pending/README.md) - every score "
                "in this artifact is provisional"
            ]
        ),
    }
    artifact["projection"] = projection_log
    artifact["source_baseline"] = {
        "available": source_artifact is not None,
        "path": source_artifact_path if source_artifact is not None else None,
        "note": (
            "Read only for the comparison section below - never used to "
            "compute any target score in this artifact."
            if source_artifact is not None
            else "No source-side complexity_artifact.json found next to the tree - "
                 "comparison section is empty, target scores are unaffected."
        ),
    }
    artifact["comparison"] = comparison
    return artifact, results


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Project a Normalized Tree onto a target language and run the real 20 complexity analyzers against it"
    )
    ap.add_argument("tree", help="Path to the Normalized Tree JSON (Agent 2's output)")
    ap.add_argument(
        "--target", required=True, help="Target language id, e.g. python, java, cobol, plsql"
    )
    ap.add_argument(
        "--languages-dir",
        default=os.path.join(HERE, "languages"),
    )
    ap.add_argument(
        "--source-artifact",
        default=None,
        help="Path to Agent 3's complexity_artifact.json for the comparison section "
             "(default: look for complexity_artifact.json next to the tree file)",
    )
    ap.add_argument(
        "-o",
        "--out-dir",
        default=None,
        help="Override output location (default: <tree_dir>/target/<target>/)",
    )
    args = ap.parse_args(argv)

    artifact, results = analyze(args.tree, args.target, args.languages_dir, args.source_artifact)

    out_dir = args.out_dir or os.path.join(os.path.dirname(os.path.abspath(args.tree)), "target", args.target)
    os.makedirs(os.path.join(out_dir, "reports"), exist_ok=True)
    for r in results:
        with open(os.path.join(out_dir, "reports", f"{r['sno']:02d}_{r['id']}.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(r, fh, indent=2, sort_keys=True)
    out_path = os.path.join(out_dir, "complexity_artifact.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, sort_keys=True)
        f.write("\n")

    cov = artifact["coverage"]
    proj = artifact["projection"]
    print(f"target-fit: {artifact['source_language']} -> {args.target}", file=sys.stderr)
    print(
        f"  projected {proj['units_projected']}/{proj['units_total_source']} unit(s) "
        f"({len(proj['units_dropped'])} dropped)",
        file=sys.stderr,
    )
    print(
        f"  measured {cov['analyzers_ok']}/{cov['analyzers_discovered']} "
        f"({round(cov['completeness'] * 100)}%)   overall level {artifact['overall']['level']}",
        file=sys.stderr,
    )
    if not artifact["descriptor_reviewed"]:
        print(f"  NOTE: descriptor for '{args.target}' is unreviewed - confidence reduced", file=sys.stderr)
    print(f"  -> {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
