"""
project_tree.py — projects a source Normalized Tree onto a target language.

What is it?      Takes the tree Agent 2 produced and one target-language
                 capability descriptor, and produces a second, structurally
                 valid Normalized Tree representing what a FAITHFUL
                 translation's shape would be - never real target source
                 code, never a guess at one.
Why needed?      Every one of the 20 complexity analyzers is a pure function
                 over a Normalized Tree (analyze(tree) -> dict). If the
                 projected tree is itself a valid Normalized Tree, those same
                 20 analyzers - unmodified, unduplicated - can be run a
                 second time against it, and the target-language scores that
                 come back are genuinely computed, not carried over or
                 reweighted from the source run.
How it works?    Three generic, target-agnostic rules, driven entirely by
                 the target descriptor's already-existing capability fields
                 (never a hardcoded source/target language pair):

                 1. JUMP CONSTRUCTS. Any unit containing a GOTO/ALTER/
                    PERFORM_THRU/FALL_THROUGH node the target cannot express
                    (per its supports_goto / supports_alter_style_dynamic_jump
                    fields) is DROPPED from the projected tree - not kept
                    with an invented rewritten shape, not left in with a
                    stripped-down CFG that would look falsely simple. Every
                    drop is logged with its reason. A target that itself
                    supports the construct (e.g. projecting COBOL onto
                    another COBOL-like target) keeps the node unchanged.

                 2. OBJECT MODEL. If the target descriptor declares no class/
                    object model (multiple_inheritance is None, e.g. COBOL),
                    `types` is dropped from the projected tree entirely - the
                    concept of a class hierarchy has nothing to project onto.
                    Analyzers that require `types` (Cohesion, Inheritance)
                    then gate to insufficient_input through the SAME central
                    mechanism _core.py already enforces for every analyzer -
                    no special-casing needed here.

                 3. VOLUME FIELDS. `loc`, `comment_lines` and `halstead` are
                    stripped from every unit, for every target, always. There
                    is no honest way to project the real size of code that
                    does not exist yet, and this project explicitly refuses
                    to invent a verbosity/expansion ratio to estimate one.
                    Stripping these fields makes Structural Complexity and
                    Maintainability Complexity gate to insufficient_input
                    through their own declared `requires`/`optional`, the
                    same central mechanism as above.

                 Everything else - references, writes, globals, params, meta,
                 sql, cursors, transactions, platform_calls,
                 dynamic_constructs, config_reads, feature_flags,
                 conditional_compilation, literals, call_graph,
                 dependency_graph - is a fact about what the code DOES, not
                 about the language expressing it, and is carried through
                 unchanged.
Input required   A Normalized Tree (dict) and one target descriptor (dict,
                 same shape as .claude/target_fit/languages/*.json).

Pure function, standard library only, same contract as every analyzer in
.claude/complexities/ - see docs/analyzer-contract.md.
"""
import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "complexities"))
from _core import JUMP_NODES, Tree  # noqa: E402

VOLUME_FIELDS = ("loc", "comment_lines", "halstead")

# Which descriptor capability flag governs each jump node type. Generic -
# every target's descriptor already declares these two flags; nothing here
# is specific to any one source or target language.
_JUMP_FLAG = {
    "ALTER": "supports_alter_style_dynamic_jump",
    "GOTO": "supports_goto",
    "PERFORM_THRU": "supports_goto",
    "FALL_THROUGH": "supports_goto",
}


def _unit_jump_blockers(unit, descriptor):
    """Which jump node types in this unit's CFG the target cannot express."""
    blockers = []
    cfg = unit.get("cfg") or {}
    seen_types = {node.get("node_type") for node in Tree.walk(cfg)} & JUMP_NODES
    for node_type in sorted(seen_types):
        flag = _JUMP_FLAG.get(node_type)
        if flag and not descriptor.get(flag, False):
            blockers.append(node_type)
    return blockers


def project_tree(source_tree_raw, descriptor):
    """Returns (projected_tree_raw, projection_log).

    projection_log is a plain dict recording every generic rule that fired,
    so the target artifact can state exactly what changed and why - never a
    silent transformation.
    """
    target_id = descriptor.get("id", "unknown")
    target_name = descriptor.get("display_name", target_id)
    tree = copy.deepcopy(source_tree_raw)
    source_units = tree.get("units") or []

    kept_units = []
    dropped_units = []
    for unit in source_units:
        blockers = _unit_jump_blockers(unit, descriptor)
        if blockers:
            dropped_units.append({
                "unit": unit.get("id"),
                "reason": (
                    f"contains {', '.join(blockers)} construct(s) that {target_name} "
                    f"cannot express (per its capability descriptor) - no mechanical "
                    f"rewrite is attempted; this unit is excluded from the projected "
                    f"tree rather than given an invented restructured shape"
                ),
            })
            continue
        # Strip volume fields - never projected, for any target.
        projected_unit = dict(unit)
        stripped_here = [f for f in VOLUME_FIELDS if f in projected_unit]
        for field in stripped_here:
            del projected_unit[field]
        kept_units.append(projected_unit)

    tree["units"] = kept_units

    has_object_model = descriptor.get("multiple_inheritance") is not None
    types_dropped = False
    if not has_object_model and tree.get("types"):
        types_dropped = True
        tree["types"] = []

    tree["language"] = target_id
    tree["projected_from"] = source_tree_raw.get("language", "unknown")
    tree.pop("target_language", None)

    log = {
        "target_language": target_id,
        "source_language": source_tree_raw.get("language", "unknown"),
        "units_total_source": len(source_units),
        "units_projected": len(kept_units),
        "units_dropped": dropped_units,
        "fields_stripped_every_unit": list(VOLUME_FIELDS),
        "fields_stripped_reason": (
            "loc/comment_lines/halstead describe the volume of source-language "
            "text; projecting them onto a target without real target code would "
            "require an invented verbosity ratio, which this design refuses to do"
        ),
        "fields_stripped_caveat": (
            "For an analyzer that declares one of these fields REQUIRED (e.g. "
            "Maintainability Complexity needs loc), stripping it correctly gates "
            "the metric to insufficient_input - the honest outcome. But for an "
            "analyzer that only declares it OPTIONAL (e.g. Migration Complexity), "
            "the analyzer's own existing internal code substitutes a default of "
            "zero for the missing value rather than refusing to score - this is "
            "pre-existing, already-audited behavior of that analyzer (and its "
            "confidence score drops accordingly, naming loc in "
            "confidence.reasons), not something this projection can or should "
            "patch. A target score that moved compared to the source baseline "
            "for a reason like this reflects a stripped optional field defaulting "
            "toward zero, not a genuine reduction in target-language effort - "
            "check each metric's own confidence.reasons before reading a "
            "score difference as a real finding."
        ),
        "object_model_dropped": types_dropped,
        "object_model_dropped_reason": (
            f"{target_name} has no class/object model (descriptor's "
            f"multiple_inheritance is null) - `types` has nothing to project onto"
            if types_dropped else None
        ),
    }
    return tree, log
