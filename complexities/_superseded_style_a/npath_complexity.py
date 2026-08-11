"""
NPath Complexity analyzer (Nejmeh, 1988).

Input: the same generic, language-agnostic syntax tree as the other
complexity scripts (JSON via stdin, a single file, or batch mode over
tests/). Only node "kind" values are inspected, never raw source, so this
works for any language whose adapter emits this shape.

NPath counts the number of distinct ACYCLIC execution paths through a
function -- unlike cyclomatic complexity (which counts branch points) or
cognitive complexity (which weighs readability), NPath answers "how many
genuinely different routes through this code would a test suite need to
cover." It grows MULTIPLICATIVELY for independent sequential branches and
ADDITIVELY for mutually-exclusive branches of the same decision -- that
multiplicative growth is the "path explosion" this metric exists to catch:
a method can look mild by cyclomatic complexity (few branch points) yet
have thousands of NPath routes if those branches are sequential rather than
nested.

Core rules (per statement/construct, standard NPath definition):
  - a simple statement (leaf, or any kind this script doesn't recognize) = 1 path
  - a SEQUENCE of sibling statements/constructs MULTIPLIES their path counts
    (for every path through statement A, you can combine it with every path
    through statement B that follows it)
  - an if/elif/.../else chain SUMS its branches' path counts (only one
    branch executes per run, so these are mutually exclusive, not
    sequential) plus 1 extra path per && / || in each branch's own
    condition (short-circuit evaluation is itself a fork), plus +1 overall
    if the chain has no trailing `else` (the "nothing matched" path)
  - a switch/case SUMS its cases' path counts, +1 if there's no
    `default_clause` (the "nothing matched" path), same as if/else
  - a loop (for/while/do_while/until) = body-path-count + condition
    &&/|| count + 1 (the +1 is the zero-iteration / loop-exit path)
  - a ternary = 2 (true-expr, false-expr) + &&/|| count in its own condition
    -- simplified: nested branching inside a ternary's arms is not modeled,
    since that's rare in COBOL/PL-SQL/Java legacy code and the generic tree
    doesn't distinguish a ternary's arms from each other structurally
  - try/catch/finally: (try-body-paths + sum of each catch's paths), then
    MULTIPLIED by the finally block's own path count if present (finally
    always runs afterward, regardless of which path was taken, so its
    internal branching multiplies against whichever path preceded it)

IMPORTANT: unlike cognitive_complexity.py, boolean operators here are NOT
deduped by "run" -- `a && b && c` contributes 2 extra paths (one per
operator), matching the classical NPath definition, where cognitive
complexity intentionally counts a same-operator run as one mental unit.
This is a deliberate difference between the two metrics, not an
inconsistency.

Expected node shape: identical to cyclomatic_complexity.py.

Scope kinds (NPath is reported per scope): program, module, function,
method, procedure, paragraph. `program`/`module` containers are only
counted in file-level totals if their own NPath (excluding nested scopes)
exceeds the baseline of 1 (i.e. they hold real branching logic directly).

Constructs used ONLY by this script (adapters must use these kinds for
NPath to work; other scripts ignore them as structural passthrough):
    try_block    -- wraps: body statements, then catch/except children,
                    then an optional trailing finally_block child
    finally_block -- the finally clause's body

KNOWN LIMITATIONS:
  - `if`/`elif`/`else` must be emitted as consecutive SIBLINGS (same
    convention as cognitive_complexity.py) for chain-grouping to work.
  - labeled_jump (break/continue/goto) and recursive `call` nodes are not
    specially modeled -- NPath's classical definition assumes structured,
    single-entry/single-exit constructs, and both are treated as ordinary
    statements (path count 1).
  - Results can legitimately be very large (that's the point -- it's the
    signal for path explosion). Python's arbitrary-precision ints handle
    this without overflow.
  - file_level total/average across multiple functions is provided for
    schema consistency with the other complexity reports, but NPath is
    fundamentally a PER-FUNCTION measure -- `max_complexity` (the single
    riskiest function) is the number worth acting on, not the file sum.

Usage: identical to cyclomatic_complexity.py
    python npath_complexity.py                          # batch: every *.json in tests/ -> outputs/
    python npath_complexity.py tree.json                # single file -> outputs/<name>/npath_complexity.json
    python npath_complexity.py tree.json -o out.json     # single file -> explicit output path
    cat tree.json | python npath_complexity.py           # single tree via stdin -> outputs/
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

LOOP_KINDS = {"for", "while", "do_while", "until"}
BOOLEAN_OPERATOR_KINDS = {"boolean_and", "boolean_or"}

MODULE_LEVEL_SCOPE_NAME = "MODULE_LEVEL"


def count_boolean_ops_direct(node: dict[str, Any]) -> int:
    return sum(1 for c in node.get("children", []) if c.get("kind") in BOOLEAN_OPERATOR_KINDS)


def npath_if_chain(chain: list[dict[str, Any]], has_else: bool) -> int:
    branch_sum = 0
    condition_extra = 0
    for branch in chain:
        branch_sum += path_count(branch.get("children", []))
        if branch.get("kind") in ("if", "elif"):
            condition_extra += count_boolean_ops_direct(branch)
    return branch_sum + condition_extra + (0 if has_else else 1)


def npath_switch(node: dict[str, Any]) -> int:
    cases = [c for c in node.get("children", []) if c.get("kind") in ("case_clause", "default_clause")]
    has_default = any(c.get("kind") == "default_clause" for c in cases)
    case_sum = sum(path_count(c.get("children", [])) for c in cases)
    selector_extra = count_boolean_ops_direct(node)
    return case_sum + selector_extra + (0 if has_default else 1)


def npath_loop(node: dict[str, Any]) -> int:
    body_path = path_count(node.get("children", []))
    condition_extra = count_boolean_ops_direct(node)
    return body_path + condition_extra + 1


def npath_try(node: dict[str, Any]) -> int:
    body_children: list[dict[str, Any]] = []
    catches: list[dict[str, Any]] = []
    finally_node: dict[str, Any] | None = None
    for c in node.get("children", []):
        kind = c.get("kind")
        if kind in ("catch", "except"):
            catches.append(c)
        elif kind == "finally_block":
            finally_node = c
        else:
            body_children.append(c)
    base = path_count(body_children) + sum(path_count(c.get("children", [])) for c in catches)
    if finally_node is not None:
        return base * path_count(finally_node.get("children", []))
    return base


def path_count(children: list[dict[str, Any]]) -> int:
    total = 1
    i = 0
    n = len(children)
    while i < n:
        child = children[i]
        kind = child.get("kind")

        if kind in SCOPE_KINDS:
            i += 1
            continue  # nested scope, reported separately

        if kind == "if":
            chain = [child]
            j = i + 1
            while j < n and children[j].get("kind") == "elif":
                chain.append(children[j])
                j += 1
            has_else = j < n and children[j].get("kind") == "else"
            if has_else:
                chain.append(children[j])
                j += 1
            total *= npath_if_chain(chain, has_else)
            i = j
            continue

        if kind == "switch_statement":
            total *= npath_switch(child)
            i += 1
            continue

        if kind == "try_block":
            total *= npath_try(child)
            i += 1
            continue

        if kind in LOOP_KINDS:
            total *= npath_loop(child)
            i += 1
            continue

        if kind == "ternary":
            total *= (2 + count_boolean_ops_direct(child))
            i += 1
            continue

        # structural passthrough / simple statement
        sub_children = child.get("children", [])
        total *= path_count(sub_children) if sub_children else 1
        i += 1

    return total


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
        npath = path_count(node.get("children", []))
        scopes.append({
            "scope_kind": node.get("kind"),
            "name": node.get("name") or node.get("label") or MODULE_LEVEL_SCOPE_NAME,
            "start_line": node.get("start_line"),
            "end_line": node.get("end_line"),
            "complexity": npath,
            "in_totals": node.get("kind") in UNIT_SCOPE_KINDS or npath > 1,
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
        "complexity_type": "npath_complexity",
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
    return os.path.join(output_dir, stem, "npath_complexity.json")


def process_tree(root: dict[str, Any], output_path: str, source_file: str | None, language: str) -> None:
    artifact = build_artifact(root, source_file, language)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    print(f"Artifact written to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute NPath complexity from a generic IR tree.")
    parser.add_argument("input", nargs="?", help="Path to a single input IR tree JSON. Omit (with no piped stdin) to batch-process every *.json in --input-dir.")
    parser.add_argument("-o", "--output", help="Output path for single-file mode (default: <output-dir>/<name>/npath_complexity.json)")
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