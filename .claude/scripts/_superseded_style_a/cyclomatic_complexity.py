"""
Cyclomatic Complexity analyzer.

Input: a generic, language-agnostic syntax tree as JSON (stdin, or a file
path passed as the first CLI arg). This script never looks at raw source or
language-specific syntax -- it only recognizes a canonical vocabulary of
node "kind" values, so the same script works for any language (COBOL,
PL/SQL, Java, Python, ...) as long as the tree uses this shape. Producing
that tree from a real per-language AST is a separate, upstream concern.

Expected node shape:
    {
      "kind": "if",            # canonical category -- see *_KINDS below
      "label": "IF",            # original source token, kept for traceability only
      "name": null,              # function/method/paragraph/procedure name (scope nodes only)
      "start_line": 52,
      "end_line": 55,
      "children": [ ... ]
    }

Scope kinds (complexity is reported per scope):
    program, module, function, method, procedure, paragraph

Decision kinds (+1 each):
    if, elif, for, while, do_while, until, case_clause, when_clause,
    catch, except, ternary

Boolean operator kinds (+1 each -- short-circuit operators add a path):
    boolean_and, boolean_or

NOT decision points, on purpose -- adapters must use these exact kinds for
the default/fallthrough branch of a case-like construct (Java `default:`,
COBOL `WHEN OTHER`, Python `case _:`), since it does not add a new path:
    default_clause

If the root node isn't a scope kind, it's treated as an implicit module-level
scope (e.g. top-level COBOL PROCEDURE DIVISION code with no paragraphs, or
top-level script statements). Nested scopes are reported separately and do
not contribute to their parent's count.

`program` and `module` are container scopes: they exist to group other
scopes (a COBOL program's paragraphs, a Java file's top-level statements)
and are only scored/counted in the file-level totals if they carry at least
one decision point of their own. A pure container with no direct logic
still appears in the `scopes` list (marked `"in_totals": false`) for
structural context, but doesn't skew `total_complexity` / `average_complexity`.

Usage:
    python cyclomatic_complexity.py                          # batch: every *.json in tests/ -> outputs/
    python cyclomatic_complexity.py tree.json                # single file -> outputs/<name>.cyclomatic_complexity.json
    python cyclomatic_complexity.py tree.json -o out.json     # single file -> explicit output path
    cat tree.json | python cyclomatic_complexity.py           # single tree via stdin -> outputs/
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

DECISION_KINDS = {
    "if", "elif", "for", "while", "do_while", "until",
    "case_clause", "when_clause", "catch", "except", "ternary",
}

BOOLEAN_OPERATOR_KINDS = {"boolean_and", "boolean_or"}

DECISION_POINT_KINDS = DECISION_KINDS | BOOLEAN_OPERATOR_KINDS

MODULE_LEVEL_SCOPE_NAME = "MODULE_LEVEL"


def analyze(root: dict[str, Any]) -> list[dict[str, Any]]:
    """Walk the tree once, bucketing decision points by their nearest
    enclosing scope. Returns one report entry per scope."""
    if root.get("kind") not in SCOPE_KINDS:
        root = {
            "kind": "module",
            "name": MODULE_LEVEL_SCOPE_NAME,
            "start_line": root.get("start_line"),
            "end_line": root.get("end_line"),
            "children": [root],
        }

    scopes: list[dict[str, Any]] = []

    def new_scope_record(node: dict[str, Any]) -> dict[str, Any]:
        record = {
            "scope_kind": node.get("kind"),
            "name": node.get("name") or node.get("label") or MODULE_LEVEL_SCOPE_NAME,
            "start_line": node.get("start_line"),
            "end_line": node.get("end_line"),
            "decision_points": [],
        }
        scopes.append(record)
        return record

    def walk(node: dict[str, Any], scope: dict[str, Any]) -> None:
        for child in node.get("children", []):
            kind = child.get("kind")
            if kind in SCOPE_KINDS:
                walk(child, new_scope_record(child))
                continue
            if kind in DECISION_POINT_KINDS:
                scope["decision_points"].append({
                    "kind": kind,
                    "label": child.get("label"),
                    "line": child.get("start_line"),
                })
            walk(child, scope)

    walk(root, new_scope_record(root))

    for s in scopes:
        s["complexity"] = 1 + len(s["decision_points"])
        # A container (program/module) only counts as a scored unit if it
        # holds decision points directly; otherwise it's pure structure and
        # would just dilute the file-level averages.
        s["in_totals"] = s["scope_kind"] in UNIT_SCOPE_KINDS or len(s["decision_points"]) > 0

    return scopes


def build_artifact(root: dict[str, Any], source_file: str | None, language: str) -> dict[str, Any]:
    scopes = analyze(root)
    scored = [s for s in scopes if s["in_totals"]]
    total = sum(s["complexity"] for s in scored)
    return {
        "complexity_type": "cyclomatic_complexity",
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
    return os.path.join(output_dir, stem, "cyclomatic_complexity.json")


def process_tree(root: dict[str, Any], output_path: str, source_file: str | None, language: str) -> None:
    artifact = build_artifact(root, source_file, language)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    print(f"Artifact written to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute cyclomatic complexity from a generic IR tree.")
    parser.add_argument("input", nargs="?", help="Path to a single input IR tree JSON. Omit (with no piped stdin) to batch-process every *.json in --input-dir.")
    parser.add_argument("-o", "--output", help="Output path for single-file mode (default: <output-dir>/<name>/cyclomatic_complexity.json)")
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
