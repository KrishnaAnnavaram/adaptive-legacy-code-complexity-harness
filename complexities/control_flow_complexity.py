"""
Control Flow Complexity analyzer.

Input: the same generic, language-agnostic syntax tree as the other
complexity scripts (JSON via stdin, a single file, or batch mode over
tests/). Only node "kind" values are inspected, never raw source, so this
works for any language whose adapter emits this shape.

This is deliberately built on the SAME underlying signals as
cyclomatic_complexity.py (branches, loops, boolean operators) PLUS the
things a pure decision-count metric misses: unstructured jumps, multiple
exit points, and recursion -- i.e. this is what cyclomatic complexity
becomes once you stop assuming fully structured, single-exit control flow.
Where this script's score for a scope equals cyclomatic's score for the
same scope, that scope has clean structured flow (no jumps, at most one
exit, no self-recursion); a gap between the two numbers is itself signal.

Branch kinds (+1 each -- same set as cyclomatic_complexity.py's decision
points, minus loops which are broken out separately below):
    if, elif, case_clause, when_clause, catch, except, ternary

Loop kinds (+1 each -- reported as a separate category from "branch" purely
for breakdown clarity; both contribute the same +1, since a loop's decision
node has the same 2-way out-degree as an if in CFG terms):
    for, while, do_while, until

Boolean operator kinds (+1 each -- short-circuit evaluation forks the flow):
    boolean_and, boolean_or

Jump kinds (+1 each -- an edge the branch/loop count above does NOT already
capture, since it exits the enclosing construct through a non-local edge):
    labeled_jump

Exit kinds -- `return_statement` marks an explicit exit point. A single
exit (or none, i.e. implicit fall-through) is normal and free; every
ADDITIONAL return beyond the first is +1, since each extra explicit exit is
another edge straight to the scope's exit node, on top of whatever the
branch/loop count already implies:
    return_statement

Recursion (+1, direct only -- same rule and limitation as
cognitive_complexity.py): a `call` node whose label matches the enclosing
scope's name is a back-edge in the call graph.

Formula per scope:
    1 + branches + loops + boolean_ops + jumps + extra_exits + recursion

Usage: identical to cyclomatic_complexity.py
    python control_flow_complexity.py                          # batch: every *.json in tests/ -> outputs/
    python control_flow_complexity.py tree.json                # single file -> outputs/<name>/control_flow_complexity.json
    python control_flow_complexity.py tree.json -o out.json     # single file -> explicit output path
    cat tree.json | python control_flow_complexity.py           # single tree via stdin -> outputs/
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

BRANCH_KINDS = {"if", "elif", "case_clause", "when_clause", "catch", "except", "ternary"}
LOOP_KINDS = {"for", "while", "do_while", "until"}
BOOLEAN_OPERATOR_KINDS = {"boolean_and", "boolean_or"}
JUMP_KINDS = {"labeled_jump"}
EXIT_KIND = "return_statement"

MODULE_LEVEL_SCOPE_NAME = "MODULE_LEVEL"


def analyze_scope(scope_node: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    returns: list[dict[str, Any]] = []
    enclosing_unit_name = scope_node.get("name") if scope_node.get("kind") in UNIT_SCOPE_KINDS else None

    def emit(child: dict[str, Any], category: str) -> None:
        events.append({
            "kind": child.get("kind"),
            "label": child.get("label"),
            "line": child.get("start_line"),
            "category": category,
        })

    def walk(children: list[dict[str, Any]]) -> None:
        for child in children:
            kind = child.get("kind")
            if kind in SCOPE_KINDS:
                continue  # nested scope, reported separately
            if kind in BRANCH_KINDS:
                emit(child, "branch")
            elif kind in LOOP_KINDS:
                emit(child, "loop")
            elif kind in BOOLEAN_OPERATOR_KINDS:
                emit(child, "boolean_operator")
            elif kind in JUMP_KINDS:
                emit(child, "jump")
            elif kind == EXIT_KIND:
                returns.append(child)
            elif kind == "call" and enclosing_unit_name is not None and child.get("label") == enclosing_unit_name:
                emit(child, "recursion")
            walk(child.get("children", []))

    walk(scope_node.get("children", []))

    for extra_return in returns[1:]:
        emit(extra_return, "extra_exit")

    return events


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
        events = analyze_scope(node)
        breakdown = {"branch": 0, "loop": 0, "boolean_operator": 0, "jump": 0, "extra_exit": 0, "recursion": 0}
        for e in events:
            breakdown[e["category"]] += 1
        scopes.append({
            "scope_kind": node.get("kind"),
            "name": node.get("name") or node.get("label") or MODULE_LEVEL_SCOPE_NAME,
            "start_line": node.get("start_line"),
            "end_line": node.get("end_line"),
            "complexity": 1 + len(events),
            "breakdown": breakdown,
            "events": events,
            "in_totals": node.get("kind") in UNIT_SCOPE_KINDS or len(events) > 0,
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
        "complexity_type": "control_flow_complexity",
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
    return os.path.join(output_dir, stem, "control_flow_complexity.json")


def process_tree(root: dict[str, Any], output_path: str, source_file: str | None, language: str) -> None:
    artifact = build_artifact(root, source_file, language)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    print(f"Artifact written to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute control flow complexity from a generic IR tree.")
    parser.add_argument("input", nargs="?", help="Path to a single input IR tree JSON. Omit (with no piped stdin) to batch-process every *.json in --input-dir.")
    parser.add_argument("-o", "--output", help="Output path for single-file mode (default: <output-dir>/<name>/control_flow_complexity.json)")
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