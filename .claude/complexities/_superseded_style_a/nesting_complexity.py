"""
Nesting Complexity analyzer.

Input: the same generic, language-agnostic syntax tree as the other
complexity scripts (JSON via stdin, a single file, or batch mode over
tests/). Only node "kind" values are inspected, never raw source, so this
works for any language whose adapter emits this shape.

Measures how deeply control structures nest inside each other -- a strong,
simple proxy for how hard a function is to hold in your head, independent
of how many total branches it has. A function with 10 sequential
if-statements (cyclomatic complexity 11, nesting depth 1) reads very
differently from one with 10 if-statements nested inside each other
(cyclomatic complexity 11, nesting depth 10) -- this metric is what tells
those two apart.

Nesting kinds -- each one descends one level deeper for its own children:
    if, elif, else, ternary, switch_statement, for, while, do_while,
    until, try_block, catch, except, finally_block

Note this set is deliberately broader than cognitive_complexity.py's
NESTING_KINDS: cognitive complexity only charges for constructs that
represent a genuine DECISION (so it excludes `try_block`/`finally_block`,
which don't branch). Nesting complexity cares about literal block/indent
depth, and `try`/`finally` bodies really are indented one level deeper in
real source, so they count here even though they don't for cognitive
complexity. This is an intentional divergence between the two scripts, not
an inconsistency.

Same convention as cognitive_complexity.py: `if`/`elif`/`else` are emitted
as SIBLINGS representing one chain (not nested inside each other), so they
naturally land at the same depth -- no special-casing needed here, unlike
in npath_complexity.py or cognitive_complexity.py, since depth is simply
"how many enclosing nesting constructs contain this point," and siblings
share the same enclosing context by construction. `switch_statement`'s
`case_clause`/`default_clause` children are structural passthrough (they
don't add their own depth beyond the switch itself).

Expected node shape: identical to cyclomatic_complexity.py.

Scope kinds (depth is reported per scope): program, module, function,
method, procedure, paragraph. `program`/`module` containers are only
counted in file-level totals if they have at least one nesting construct
directly in them (max_depth > 0).

Per scope this reports:
    complexity            -- max nesting depth reached in this scope (the
                              primary score, used for file-level totals)
    average_nesting_depth -- mean depth across every nesting-construct
                              occurrence in this scope (secondary signal:
                              tells you whether deep nesting is a one-off
                              or pervasive throughout the function)

Usage: identical to cyclomatic_complexity.py
    python nesting_complexity.py                          # batch: every *.json in tests/ -> outputs/
    python nesting_complexity.py tree.json                # single file -> outputs/<name>/nesting_complexity.json
    python nesting_complexity.py tree.json -o out.json     # single file -> explicit output path
    cat tree.json | python nesting_complexity.py           # single tree via stdin -> outputs/
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import sys
from typing import Any

CONTAINER_SCOPE_KINDS = {"program", "module", "class", "package"}
UNIT_SCOPE_KINDS = {"function", "method", "procedure", "paragraph"}
SCOPE_KINDS = CONTAINER_SCOPE_KINDS | UNIT_SCOPE_KINDS

NESTING_KINDS = {
    "if", "elif", "else", "ternary", "switch_statement",
    "for", "while", "do_while", "until",
    "try_block", "catch", "except", "finally_block",
}

MODULE_LEVEL_SCOPE_NAME = "MODULE_LEVEL"


def measure_scope(scope_node: dict[str, Any]) -> tuple[int, float, list[dict[str, Any]]]:
    occurrences: list[dict[str, Any]] = []
    max_depth = 0

    def walk(children: list[dict[str, Any]], depth: int) -> None:
        nonlocal max_depth
        for child in children:
            kind = child.get("kind")
            if kind in SCOPE_KINDS:
                continue  # nested scope, reported separately
            if kind in NESTING_KINDS:
                new_depth = depth + 1
                max_depth = max(max_depth, new_depth)
                occurrences.append({
                    "kind": kind,
                    "label": child.get("label"),
                    "line": child.get("start_line"),
                    "depth": new_depth,
                })
                walk(child.get("children", []), new_depth)
                continue
            # structural passthrough, same depth
            walk(child.get("children", []), depth)

    walk(scope_node.get("children", []), 0)
    avg_depth = round(sum(o["depth"] for o in occurrences) / len(occurrences), 2) if occurrences else 0
    return max_depth, avg_depth, occurrences


def analyze(root: dict[str, Any]) -> list[dict[str, Any]]:
    if root.get("kind") not in SCOPE_KINDS:
        root = {
            "kind": "module",
            "name": MODULE_LEVEL_SCOPE_NAME,
            "start_line": root.get("start_line"),
            "end_line": root.get("end_line"),
            "children": [root],
        }

    scopes: list[dict[str, Any]] = []

    def collect(node: dict[str, Any]) -> None:
        max_depth, avg_depth, occurrences = measure_scope(node)
        scopes.append({
            "scope_kind": node.get("kind"),
            "name": node.get("name") or node.get("label") or MODULE_LEVEL_SCOPE_NAME,
            "start_line": node.get("start_line"),
            "end_line": node.get("end_line"),
            "complexity": max_depth,
            "average_nesting_depth": avg_depth,
            "nesting_points": occurrences,
            "in_totals": node.get("kind") in UNIT_SCOPE_KINDS or max_depth > 0,
        })
        for child in node.get("children", []):
            if child.get("kind") in SCOPE_KINDS:
                collect(child)

    collect(root)
    return scopes


def build_artifact(root: dict[str, Any], source_file: str | None, language: str) -> dict[str, Any]:
    scopes = analyze(root)
    scored = [s for s in scopes if s["in_totals"]]
    total = sum(s["complexity"] for s in scored)
    return {
        "complexity_type": "nesting_complexity",
        "source_file": source_file,
        "language": language,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "file_level": {
            "total_complexity": total,
            "average_complexity": round(total / len(scored), 2) if scored else 0,
            "max_complexity": max((s["complexity"] for s in scored), default=0),
            "scope_count": len(scored),
        },
        "scopes": scopes,
    }


def default_output_path(output_dir: str, input_path: str | None, source_file: str | None) -> str:
    stem_source = source_file or input_path or "artifact"
    stem = os.path.splitext(os.path.basename(stem_source))[0]
    return os.path.join(output_dir, stem, "nesting_complexity.json")


def process_tree(root: dict[str, Any], output_path: str, source_file: str | None, language: str) -> None:
    artifact = build_artifact(root, source_file, language)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    print(f"Artifact written to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute nesting complexity from a generic IR tree.")
    parser.add_argument("input", nargs="?", help="Path to a single input IR tree JSON. Omit (with no piped stdin) to batch-process every *.json in --input-dir.")
    parser.add_argument("-o", "--output", help="Output path for single-file mode (default: <output-dir>/<name>/nesting_complexity.json)")
    parser.add_argument("--input-dir", default="tests", help="Folder to batch-read tree JSON files from when no single input file is given (default: tests)")
    parser.add_argument("--output-dir", default="outputs", help="Folder to write artifacts to (default: outputs)")
    parser.add_argument("--language", default="unknown", help="Source language label for the report")
    parser.add_argument("--source-file", default=None, help="Original source file path for the report (single-file mode only)")
    args = parser.parse_args()

    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            root = json.load(f)
        output_path = args.output or default_output_path(args.output_dir, args.input, args.source_file)
        process_tree(root, output_path, args.source_file or args.input, args.language)
        return

    if not sys.stdin.isatty():
        root = json.load(sys.stdin)
        output_path = args.output or default_output_path(args.output_dir, None, args.source_file)
        process_tree(root, output_path, args.source_file, args.language)
        return

    tree_files = sorted(glob.glob(os.path.join(args.input_dir, "*.json")))
    if not tree_files:
        print(f"No .json tree files found in {args.input_dir}")
        return
    for tree_file in tree_files:
        with open(tree_file, "r", encoding="utf-8") as f:
            root = json.load(f)
        output_path = default_output_path(args.output_dir, tree_file, None)
        process_tree(root, output_path, tree_file, args.language)


if __name__ == "__main__":
    main()