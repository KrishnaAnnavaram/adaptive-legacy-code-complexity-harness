"""
Cognitive Complexity analyzer (SonarSource-style).

Input: the same kind of generic, language-agnostic syntax tree as
cyclomatic_complexity.py -- JSON via stdin, a single file, or batch mode
over tests/. This script only ever inspects node "kind" values, never raw
source, so it works for any language whose adapter emits this shape.

Cognitive complexity differs from cyclomatic complexity in what it's trying
to measure: not "how many paths through this code," but "how hard is this
for a human to hold in their head." Concretely that means:
  - nested control structures cost MORE than flat ones (a deeply nested if
    is harder to read than the same if at the top level)
  - a switch/case statement costs the same regardless of how many cases it
    has (unlike cyclomatic, which charges per case)
  - a chain of the same boolean operator (a && b && c) is one mental unit,
    not three
  - jumping out of the normal flow (break/continue/goto to a label) costs,
    even though it doesn't add a branch in the cyclomatic sense
  - a function calling itself (recursion) costs, even though it's zero
    additional branches

Expected node shape (identical to cyclomatic_complexity.py):
    {
      "kind": "if",
      "label": "IF",
      "name": null,
      "start_line": 52,
      "end_line": 55,
      "children": [ ... ]
    }

Scope kinds (score is reported per scope, same as cyclomatic):
    program, module, function, method, procedure, paragraph
`program`/`module` are containers -- only scored/counted in file-level
totals if they carry an increment directly (see cyclomatic_complexity.py
for the same convention).

Nesting-increment kinds -- each contributes (1 + current_nesting_level),
and each opens one extra level of nesting for its own children:
    if, elif, else, ternary, switch_statement, for, while, do_while,
    until, catch, except

IMPORTANT convention: if / elif / else are emitted as SIBLINGS (children of
the same enclosing node), representing one chain -- NOT nested inside each
other. All three score at the SAME nesting level; only each branch's own
children (its body) go one level deeper. This is what keeps an if/elif/else
chain from being penalized as if it were 3 levels of nesting. A genuinely
new `if` nested inside another branch's body is just another child further
down the tree, and picks up the nesting bonus normally.

`switch_statement` wraps `case_clause` / `default_clause` children, which
are purely structural (not counted individually -- that's the point:
cognitive complexity doesn't charge per case). Their own children (each
case's body) are walked one level deeper than the switch, same as any
other nesting kind.

Flat-increment kinds -- always +1, no nesting bonus, regardless of depth:
    labeled_jump           (goto LABEL / break LABEL / continue LABEL)
    boolean_and, boolean_or (see run-dedup rule below)

Boolean operator run-dedup: consecutive SIBLINGS of the same operator kind
count as one increment (a && b && c -> +1 total), but switching operator
kind, or any non-operator sibling in between, starts a new run (a && b || c
-> +2; the interruption resets tracking). This is an approximation of the
official spec's "sequence of binary logical operators" rule -- it assumes
adapters emit a condition's operator nodes as siblings in source order.

Recursion (+1 flat, no nesting bonus): a `call` node whose `label` matches
the name of its nearest enclosing unit scope (function/method/procedure/
paragraph) is treated as direct self-recursion. KNOWN LIMITATION: this only
catches direct recursion (A calls A). Indirect/mutual recursion (A calls B
calls A) is not detected -- that needs a whole-program call graph, which is
out of scope here.

Usage: identical to cyclomatic_complexity.py
    python cognitive_complexity.py                          # batch: every *.json in tests/ -> outputs/
    python cognitive_complexity.py tree.json                # single file -> outputs/<name>.cognitive_complexity.json
    python cognitive_complexity.py tree.json -o out.json     # single file -> explicit output path
    cat tree.json | python cognitive_complexity.py           # single tree via stdin -> outputs/
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
    "for", "while", "do_while", "until", "catch", "except",
}

FLAT_KINDS = {"labeled_jump"}

BOOLEAN_OPERATOR_KINDS = {"boolean_and", "boolean_or"}

MODULE_LEVEL_SCOPE_NAME = "MODULE_LEVEL"


def score_scope(scope_node: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    """Walk one scope's subtree once, returning (total_score, increment_events).
    Stops descending at a nested scope -- that scope is scored separately."""
    events: list[dict[str, Any]] = []
    total = 0
    enclosing_unit_name = scope_node.get("name") if scope_node.get("kind") in UNIT_SCOPE_KINDS else None

    def record(child: dict[str, Any], nesting_level: int, points: int, reason: str) -> None:
        nonlocal total
        total += points
        events.append({
            "kind": child.get("kind"),
            "label": child.get("label"),
            "line": child.get("start_line"),
            "nesting_level": nesting_level,
            "points": points,
            "reason": reason,
        })

    def walk(children: list[dict[str, Any]], nesting_level: int) -> None:
        last_bool_kind: str | None = None
        for child in children:
            kind = child.get("kind")

            if kind in SCOPE_KINDS:
                last_bool_kind = None
                continue  # nested scope, reported separately

            if kind in NESTING_KINDS:
                record(child, nesting_level, 1 + nesting_level, "nesting_structure")
                walk(child.get("children", []), nesting_level + 1)
                last_bool_kind = None
                continue

            if kind in BOOLEAN_OPERATOR_KINDS:
                if kind != last_bool_kind:
                    record(child, nesting_level, 1, "boolean_operator_run")
                last_bool_kind = kind
                walk(child.get("children", []), nesting_level)
                continue

            if kind in FLAT_KINDS:
                record(child, nesting_level, 1, "labeled_jump")
                last_bool_kind = None
                walk(child.get("children", []), nesting_level)
                continue

            if kind == "call" and enclosing_unit_name is not None and child.get("label") == enclosing_unit_name:
                record(child, nesting_level, 1, "direct_recursion")
                last_bool_kind = None
                continue

            # structural passthrough (block, case_clause, default_clause, assignment, ...)
            last_bool_kind = None
            walk(child.get("children", []), nesting_level)

    walk(scope_node.get("children", []), 0)
    return total, events


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
        complexity, events = score_scope(node)
        scopes.append({
            "scope_kind": node.get("kind"),
            "name": node.get("name") or node.get("label") or MODULE_LEVEL_SCOPE_NAME,
            "start_line": node.get("start_line"),
            "end_line": node.get("end_line"),
            "complexity": complexity,
            "increments": events,
            "in_totals": node.get("kind") in UNIT_SCOPE_KINDS or complexity > 0,
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
        "complexity_type": "cognitive_complexity",
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
    return os.path.join(output_dir, stem, "cognitive_complexity.json")


def process_tree(root: dict[str, Any], output_path: str, source_file: str | None, language: str) -> None:
    artifact = build_artifact(root, source_file, language)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    print(f"Artifact written to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute cognitive complexity from a generic IR tree.")
    parser.add_argument("input", nargs="?", help="Path to a single input IR tree JSON. Omit (with no piped stdin) to batch-process every *.json in --input-dir.")
    parser.add_argument("-o", "--output", help="Output path for single-file mode (default: <output-dir>/<name>/cognitive_complexity.json)")
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
