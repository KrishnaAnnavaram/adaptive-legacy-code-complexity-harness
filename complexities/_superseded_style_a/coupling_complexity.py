"""
Coupling Complexity analyzer.

Input: the same generic, language-agnostic syntax tree as the other
complexity scripts (JSON via stdin, a single file, or batch mode over
tests/). Only node "kind" values are inspected, never raw source, so this
works for any language whose adapter emits this shape.

Measures how strongly a unit depends on, and is depended on by, the rest of
the codebase -- the "blast radius" signal: how many other units break if
this one changes, and how many other things this one drags in if it moves.

KNOWN LIMITATION -- this is a SINGLE-FILE view: coupling to units outside
the current tree (a different COBOL program, another Java class in another
file) is only visible as "external" (see below), not resolved to a real
target. A true cross-file coupling picture needs a whole-codebase call
graph, which is out of scope here (same category of limitation as NPath's
file-level totals and cognitive/control-flow's direct-recursion-only
detection -- this script works with what's visible in one tree).

Uses two node kinds:
  - `call`   -- already used by cognitive_complexity.py and
                control_flow_complexity.py for recursion detection; here
                every call is counted, not just self-calls.
  - `import_statement` -- one per explicit import/reference (Java import,
                COBOL COPY, PL/SQL package reference). Attaches to
                whichever scope directly contains it, same as every other
                node.

For each unit (function/method/procedure/paragraph):
  - fan_out: how many `call`s it makes (efferent coupling -- what it depends on)
  - a call is INTERNAL if its label matches another unit's name defined
    anywhere in this same tree, else EXTERNAL (a library/external call, or
    a call into another file/program this script can't see)
  - fan_in: how many INTERNAL calls, made by OTHER units in this same tree,
    target this unit (afferent coupling -- who depends on it). Computed in
    a second pass once every unit's calls are known.
  - import_count: `import_statement` nodes found directly in this scope

complexity (per scope) = fan_out + fan_in + import_count

IMPORTANT: file_level.total_complexity is the sum of every scope's
complexity, same convention as the other scripts -- but every INTERNAL
call is counted twice by construction (once as the caller's fan_out, once
as the callee's fan_in), so the file total is not a clean "how much
coupling exists in this file" number. max_complexity (the single most
coupled unit) is the number worth acting on, same caveat as
npath_complexity.py's file-level totals.

Usage: identical to cyclomatic_complexity.py
    python coupling_complexity.py                          # batch: every *.json in tests/ -> outputs/
    python coupling_complexity.py tree.json                # single file -> outputs/<name>/coupling_complexity.json
    python coupling_complexity.py tree.json -o out.json     # single file -> explicit output path
    cat tree.json | python coupling_complexity.py           # single tree via stdin -> outputs/
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import sys
from collections import Counter
from typing import Any

CONTAINER_SCOPE_KINDS = {"program", "module", "class", "package"}
UNIT_SCOPE_KINDS = {"function", "method", "procedure", "paragraph"}
SCOPE_KINDS = CONTAINER_SCOPE_KINDS | UNIT_SCOPE_KINDS

MODULE_LEVEL_SCOPE_NAME = "MODULE_LEVEL"


def collect_local_signals(scope_node: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Calls and imports found directly in this scope, not descending into nested scopes."""
    calls: list[dict[str, Any]] = []
    imports: list[dict[str, Any]] = []

    def walk(children: list[dict[str, Any]]) -> None:
        for child in children:
            kind = child.get("kind")
            if kind in SCOPE_KINDS:
                continue
            if kind == "call":
                calls.append(child)
            elif kind == "import_statement":
                imports.append(child)
            walk(child.get("children", []))

    walk(scope_node.get("children", []))
    return calls, imports


def analyze(root: dict[str, Any]) -> list[dict[str, Any]]:
    if root.get("kind") not in SCOPE_KINDS:
        root = {
            "kind": "module",
            "name": MODULE_LEVEL_SCOPE_NAME,
            "start_line": root.get("start_line"),
            "end_line": root.get("end_line"),
            "children": [root],
        }

    raw: list[dict[str, Any]] = []

    def collect(node: dict[str, Any]) -> None:
        calls, imports = collect_local_signals(node)
        raw.append({"node": node, "calls": calls, "imports": imports})
        for child in node.get("children", []):
            if child.get("kind") in SCOPE_KINDS:
                collect(child)

    collect(root)

    unit_names = {r["node"].get("name") for r in raw if r["node"].get("kind") in UNIT_SCOPE_KINDS}
    fan_in_counter: Counter[str] = Counter()
    for r in raw:
        for call in r["calls"]:
            target = call.get("label")
            if target in unit_names:
                fan_in_counter[target] += 1

    scopes: list[dict[str, Any]] = []
    for r in raw:
        node = r["node"]
        name = node.get("name") or node.get("label") or MODULE_LEVEL_SCOPE_NAME
        internal_calls = [c for c in r["calls"] if c.get("label") in unit_names]
        external_calls = [c for c in r["calls"] if c.get("label") not in unit_names]
        fan_out = len(r["calls"])
        fan_in = fan_in_counter.get(node.get("name"), 0) if node.get("kind") in UNIT_SCOPE_KINDS else 0
        import_count = len(r["imports"])
        scopes.append({
            "scope_kind": node.get("kind"),
            "name": name,
            "start_line": node.get("start_line"),
            "end_line": node.get("end_line"),
            "fan_out": fan_out,
            "fan_in": fan_in,
            "internal_call_count": len(internal_calls),
            "external_call_count": len(external_calls),
            "import_count": import_count,
            "external_call_targets": sorted({c.get("label") for c in external_calls}),
            "import_targets": sorted({i.get("label") for i in r["imports"]}),
            "complexity": fan_out + fan_in + import_count,
            "in_totals": node.get("kind") in UNIT_SCOPE_KINDS or (fan_out + import_count) > 0,
        })
    return scopes


def build_artifact(root: dict[str, Any], source_file: str | None, language: str) -> dict[str, Any]:
    scopes = analyze(root)
    scored = [s for s in scopes if s["in_totals"]]
    total = sum(s["complexity"] for s in scored)
    external_targets: set[str] = set()
    for s in scopes:
        external_targets.update(s["external_call_targets"])
        external_targets.update(s["import_targets"])
    return {
        "complexity_type": "coupling_complexity",
        "source_file": source_file,
        "language": language,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "file_level": {
            "total_complexity": total,
            "average_complexity": round(total / len(scored), 2) if scored else 0,
            "max_complexity": max((s["complexity"] for s in scored), default=0),
            "scope_count": len(scored),
            "distinct_external_dependencies": len(external_targets),
        },
        "scopes": scopes,
    }


def default_output_path(output_dir: str, input_path: str | None, source_file: str | None) -> str:
    stem_source = source_file or input_path or "artifact"
    stem = os.path.splitext(os.path.basename(stem_source))[0]
    return os.path.join(output_dir, stem, "coupling_complexity.json")


def process_tree(root: dict[str, Any], output_path: str, source_file: str | None, language: str) -> None:
    artifact = build_artifact(root, source_file, language)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    print(f"Artifact written to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute coupling complexity from a generic IR tree.")
    parser.add_argument("input", nargs="?", help="Path to a single input IR tree JSON. Omit (with no piped stdin) to batch-process every *.json in --input-dir.")
    parser.add_argument("-o", "--output", help="Output path for single-file mode (default: <output-dir>/<name>/coupling_complexity.json)")
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