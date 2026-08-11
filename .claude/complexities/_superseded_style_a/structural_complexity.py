"""
Structural Complexity analyzer.

Input: the same generic, language-agnostic syntax tree as the other
complexity scripts (JSON via stdin, a single file, or batch mode over
tests/). Only node "kind" values (and start/end lines) are inspected, never
raw source, so this works for any language whose adapter emits this shape.

Unlike the branch-counting metrics (cyclomatic, cognitive, NPath, nesting,
control flow), this one isn't about execution paths at all -- it's about
how the file's UNITS (functions/methods/procedures/paragraphs) and
CONTAINERS (programs/modules/classes/packages) are organized: how many
there are, how deeply they nest inside each other, and whether size is
spread evenly across them or dominated by one oversized unit. There is no
single universally standardized formula for this the way there is for
cyclomatic or NPath complexity -- this script's composite score is a
transparent, documented design choice, not a citation of established
literature.

Scope kinds, same as the other scripts:
    containers: program, module, class, package
    units:      function, method, procedure, paragraph
Containers may nest inside containers (e.g. a class inside a package, or a
nested class) -- `max_hierarchy_depth` measures exactly that nesting, which
is a structural/organizational depth, NOT the control-flow nesting depth
that nesting_complexity.py measures.

Per-unit size = (end_line - start_line + 1) when both are present on the
node, else falls back to a count of nodes in its subtree. This is reported
as that scope's `complexity` value.

IMPORTANT: containers are ALWAYS excluded from the size aggregates
(total/average/max/scope_count), unconditionally -- not the conditional
in_totals rule the other scripts use. A container's line span structurally
overlaps its children units' spans (the program's 100 lines already
include the paragraph's 44 lines), so summing them in would double-count
by construction, not just as a matter of taste. Containers still appear in
`scopes` (with their own size, for hierarchy context) but are always
`in_totals: false`.

file_level reports two distinct numbers, deliberately not conflated:
  - total_complexity: sum of unit sizes -- "how much code is here"
  - structural_score: unit_count + max_hierarchy_depth + round(size_imbalance_ratio)
    -- "how well organized is it," where size_imbalance_ratio =
    max_unit_size / average_unit_size (how much one unit dominates the rest)

Usage: identical to cyclomatic_complexity.py
    python structural_complexity.py                          # batch: every *.json in tests/ -> outputs/
    python structural_complexity.py tree.json                # single file -> outputs/<name>/structural_complexity.json
    python structural_complexity.py tree.json -o out.json     # single file -> explicit output path
    cat tree.json | python structural_complexity.py           # single tree via stdin -> outputs/
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

MODULE_LEVEL_SCOPE_NAME = "MODULE_LEVEL"


def count_nodes(node: dict[str, Any]) -> int:
    return 1 + sum(count_nodes(c) for c in node.get("children", []))


def scope_size(node: dict[str, Any]) -> int:
    start, end = node.get("start_line"), node.get("end_line")
    if isinstance(start, int) and isinstance(end, int) and end >= start:
        return end - start + 1
    return count_nodes(node)


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

    def collect(node: dict[str, Any], depth: int) -> None:
        is_unit = node.get("kind") in UNIT_SCOPE_KINDS
        scopes.append({
            "scope_kind": node.get("kind"),
            "name": node.get("name") or node.get("label") or MODULE_LEVEL_SCOPE_NAME,
            "start_line": node.get("start_line"),
            "end_line": node.get("end_line"),
            "scope_depth": depth,
            "complexity": scope_size(node),
            "in_totals": is_unit,
        })
        for child in node.get("children", []):
            if child.get("kind") in SCOPE_KINDS:
                collect(child, depth + 1)

    collect(root, 0)
    return scopes


def build_artifact(root: dict[str, Any], source_file: str | None, language: str) -> dict[str, Any]:
    scopes = analyze(root)
    units = [s for s in scopes if s["in_totals"]]
    containers = [s for s in scopes if not s["in_totals"]]
    total = sum(s["complexity"] for s in units)
    avg = round(total / len(units), 2) if units else 0
    max_size = max((s["complexity"] for s in units), default=0)
    max_hierarchy_depth = max((s["scope_depth"] for s in scopes), default=0)
    imbalance_ratio = round(max_size / avg, 2) if avg else 0
    structural_score = len(units) + max_hierarchy_depth + round(imbalance_ratio)
    return {
        "complexity_type": "structural_complexity",
        "source_file": source_file,
        "language": language,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "file_level": {
            "total_complexity": total,
            "average_complexity": avg,
            "max_complexity": max_size,
            "scope_count": len(units),
            "unit_count": len(units),
            "container_count": len(containers),
            "max_hierarchy_depth": max_hierarchy_depth,
            "size_imbalance_ratio": imbalance_ratio,
            "structural_score": structural_score,
        },
        "scopes": scopes,
    }


def default_output_path(output_dir: str, input_path: str | None, source_file: str | None) -> str:
    stem_source = source_file or input_path or "artifact"
    stem = os.path.splitext(os.path.basename(stem_source))[0]
    return os.path.join(output_dir, stem, "structural_complexity.json")


def process_tree(root: dict[str, Any], output_path: str, source_file: str | None, language: str) -> None:
    artifact = build_artifact(root, source_file, language)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    print(f"Artifact written to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute structural complexity from a generic IR tree.")
    parser.add_argument("input", nargs="?", help="Path to a single input IR tree JSON. Omit (with no piped stdin) to batch-process every *.json in --input-dir.")
    parser.add_argument("-o", "--output", help="Output path for single-file mode (default: <output-dir>/<name>/structural_complexity.json)")
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