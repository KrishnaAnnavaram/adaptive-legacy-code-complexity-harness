"""
_core.py — the shared contract every complexity analyzer implements.

DESIGN GOAL
-----------
An analyzer must be usable, unchanged, in three different situations:

  1. Imported as a library by any harness:      from x import analyze; analyze(tree)
  2. Run standalone from a shell:               python x.py tree.json
  3. Piped inside a build or CI step:           cat tree.json | python x.py

Anything that only works in one of those is not portable. The rules below fall
out of that requirement, plus one hard lesson from this repo's own history.

THE RULES
---------
1. PURE FUNCTION FIRST.  `analyze(tree) -> dict`. No file IO, no globals, no
   printing, no config lookup, no network. A harness can call it a thousand
   times in-process. The CLI is a thin shell around it, never the other way up.

2. ONE TREE FORMAT.  Every analyzer reads the same Normalized Tree (below).
   Two formats in one repo means N x M glue and silent mismatches.

3. SELF-DESCRIBING.  Each analyzer exports a `SPEC` naming what it needs, what
   tier it belongs to, and what it depends on. A harness can then discover,
   filter and order analyzers without hardcoding a list of names.

4. DECLARE INPUTS AND FAIL LOUD.  If the tree lacks what the analyzer needs, it
   returns status `insufficient_input` and names the missing field. It NEVER
   returns a zero score.

   This rule exists because of a real defect found in this repo: analyzers were
   returning clean-looking zeros - and in one batch, fully-formed reports built
   from hardcoded demo data - when handed input they could not read. Nothing on
   screen distinguished that from a genuine result. A wrong number that looks
   right is worse than no number, because nobody can tell it is wrong.

5. UNIFORM OUTPUT ENVELOPE.  Same shape from all analyzers, so a harness merges
   results without a special case per analyzer.

6. DETERMINISTIC.  Same tree in, same bytes out. No timestamps inside an
   analyzer's own output (the pipeline stamps the run, once). No set-iteration
   order leaking into results.

7. STANDARD LIBRARY ONLY.  Legacy modernization frequently happens air-gapped,
   where installing a package is a change request.

THE NORMALIZED TREE
-------------------
tree = {
  "language": "cobol|plsql|java|...",
  "source_file": "path",                       # optional
  "units": [ {                                 # a routine/paragraph/method
      "id","name","owner_type",                # owner_type = module/class/program
      "loc": int, "comment_lines": int,
      "start_line": int, "end_line": int,
      "params":     [name, ...],
      "references": [data_id, ...],            # data read or written
      "globals":    [data_id, ...],
      "writes":     [data_id, ...],
      "cfg": { "node_type": "SEQUENCE", "children": [...],
               "line": int, "target": str, "bounded": bool },
      "halstead": {"volume": float},
      "sql":        [ {"kind","tables","joins","subqueries","dynamic","line"} ],
      "cursors":    [ {"name","explicit","closed"} ],
      "transactions":[ {"kind":"commit|rollback|savepoint|autonomous"} ],
      "platform_calls":[ {"name","kind":"os|mq|screen|vendor|hardware"} ],
      "dynamic_constructs":[ {"kind":"dynamic_sql|reflection|eval|alter|..."} ],
      "config_reads":[ {"key","source","default"} ],
      "feature_flags":[ {"name"} ],
      "conditional_compilation":[ {"flag"} ],
      "literals":   [ {"value","kind"} ],
      "meta": {"exposed","static","nondeterministic","constructor_params"}
  }, ... ],
  "types": [ {"id","name","kind","module","fields","methods","extends","implements"} ],
  "call_graph":       {"nodes":[id],"edges":[{"from","to"}]},
  "dependency_graph": {"nodes":[id],"edges":[{"from","to","kind"}]},
  "layers": {"web":0,"service":1,"data":2},    # optional
  "module_layer": {"module_id":"layer_name"}   # optional
}

CFG node_type vocabulary (uppercase, language-neutral):
  structure  SEQUENCE BLOCK
  branch     IF ELIF ELSE CASE DEFAULT TERNARY AND OR
  loop       FOR WHILE DO_WHILE UNTIL LOOP PERFORM_UNTIL PERFORM_VARYING
             CURSOR_LOOP FOREACH
  error      CATCH FINALLY RAISE
  jump       GOTO ALTER PERFORM_THRU FALL_THROUGH RETURN EXIT
  effect     CALL SQL EXEC_SQL DB QUERY IO FILE NETWORK SCREEN DISPLAY
             PLATFORM SYSTEM SORT SEARCH

LEVELS
  L1 trivial | L2 low | L3 moderate | L4 high | L5 severe
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

CONTRACT_VERSION = "2.0"

STATUS_OK = "ok"
STATUS_INSUFFICIENT = "insufficient_input"
STATUS_ERROR = "error"

EXIT_OK = 0
EXIT_INSUFFICIENT = 2
EXIT_ERROR = 1

TIERS = ("size", "structural", "data", "coupling", "hazard", "composite")

# ---------------------------------------------------------------------------
# CFG vocabulary
# ---------------------------------------------------------------------------

BRANCH_NODES = {"IF", "ELIF", "CASE", "TERNARY", "AND", "OR", "CATCH"}
NON_BRANCH_NODES = {"ELSE", "DEFAULT", "FINALLY"}
LOOP_NODES = {"FOR", "WHILE", "DO_WHILE", "UNTIL", "LOOP", "PERFORM_UNTIL",
              "PERFORM_VARYING", "CURSOR_LOOP", "FOREACH"}
JUMP_NODES = {"GOTO", "ALTER", "PERFORM_THRU", "FALL_THROUGH"}
SQL_NODES = {"SQL", "EXEC_SQL", "DB", "QUERY"}
IO_NODES = {"IO", "FILE", "NETWORK", "SCREEN", "DISPLAY"}
EFFECT_NODES = SQL_NODES | IO_NODES | {"PLATFORM", "SYSTEM"}

#: Nodes that add an independent path. ELSE and DEFAULT are deliberately absent:
#: the path already exists as the false arm of the branch above them. Counting
#: them inflates cyclomatic complexity by one per branch across a whole codebase.
DECISION_NODES = BRANCH_NODES | LOOP_NODES

#: Nodes that open a nesting level.
NESTING_NODES = BRANCH_NODES | LOOP_NODES | {"ELSE", "FINALLY"}


class InsufficientInput(Exception):
    """The tree does not carry what this analyzer needs.

    Raise this rather than returning zero. Rule 4 exists because a clean zero
    from a starved analyzer is indistinguishable from a genuine clean result.
    """


def insufficient(reason: str) -> None:
    raise InsufficientInput(reason)


# ---------------------------------------------------------------------------
# Analyzer specification
# ---------------------------------------------------------------------------

class Spec:
    """What an analyzer is and what it needs. Read by the harness, not by humans."""

    __slots__ = ("id", "sno", "name", "tier", "requires", "requires_any",
                 "optional", "depends_on", "direction", "version", "scope", "summary")

    def __init__(self, id: str, sno: int, name: str, tier: str,
                 requires: Sequence[str] = (), optional: Sequence[str] = (),
                 requires_any: Sequence[str] = (),
                 depends_on: Sequence[int] = (), direction: str = "higher_is_worse",
                 version: str = "2.0.0", scope: str = "unit", summary: str = ""):
        if tier not in TIERS:
            raise ValueError(f"{id}: unknown tier {tier!r}; expected one of {TIERS}")
        self.id, self.sno, self.name, self.tier = id, sno, name, tier
        self.requires = tuple(requires)
        #: At least ONE of these must be present. Used where an analyzer can work
        #: from any of several signals - #18 needs config reads OR literals OR
        #: compile flags, and demanding all three would starve it needlessly.
        self.requires_any = tuple(requires_any)
        self.optional = tuple(optional)
        self.depends_on = tuple(depends_on)
        self.direction = direction
        self.version = version
        self.scope = scope
        self.summary = summary

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "sno": self.sno, "name": self.name, "tier": self.tier,
            "requires": list(self.requires), "requires_any": list(self.requires_any),
            "optional": list(self.optional),
            "depends_on": list(self.depends_on), "direction": self.direction,
            "version": self.version, "scope": self.scope, "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Tree view
# ---------------------------------------------------------------------------

class Tree:
    """Read-only navigation over a Normalized Tree, plus capability probing."""

    def __init__(self, raw: Dict[str, Any]):
        self.raw = raw or {}

    # -- basics ----------------------------------------------------------
    @property
    def language(self) -> str:
        return self.raw.get("language", "unknown")

    @property
    def source_file(self) -> Optional[str]:
        return self.raw.get("source_file")

    @property
    def units(self) -> List[Dict[str, Any]]:
        return self.raw.get("units") or []

    @property
    def types(self) -> List[Dict[str, Any]]:
        return self.raw.get("types") or []

    @property
    def call_edges(self) -> List[Dict[str, Any]]:
        return (self.raw.get("call_graph") or {}).get("edges") or []

    @property
    def dep_edges(self) -> List[Dict[str, Any]]:
        return (self.raw.get("dependency_graph") or {}).get("edges") or []

    # -- capability probing ----------------------------------------------
    def has(self, field: str) -> bool:
        """Is `field` actually populated anywhere in the tree?

        Presence of an empty list counts as ABSENT. An adapter that emits
        `"sql": []` for a unit it never inspected is indistinguishable from one
        that inspected it and found none, so the conservative reading is used
        and the analyzer reports insufficient input rather than a clean zero.
        """
        if field in ("call_graph", "call_edges"):
            return bool(self.call_edges)
        if field in ("dependency_graph", "dep_edges"):
            return bool(self.dep_edges)
        if field == "types":
            return bool(self.types)
        if field == "units":
            return bool(self.units)
        if field == "layers":
            return bool(self.raw.get("layers") and self.raw.get("module_layer"))
        if field == "cfg":
            return any((u.get("cfg") or {}).get("children") is not None
                       for u in self.units)
        return any(u.get(field) for u in self.units)

    def capabilities(self) -> Dict[str, bool]:
        fields = ("units", "cfg", "loc", "comment_lines", "params", "references",
                  "globals", "writes", "halstead", "sql", "cursors", "transactions",
                  "platform_calls", "dynamic_constructs", "config_reads",
                  "feature_flags", "conditional_compilation", "literals", "meta",
                  "types", "call_graph", "dependency_graph", "layers")
        return {f: self.has(f) for f in fields}

    def require(self, spec: "Spec") -> List[str]:
        """Enforce Rule 4. Returns the satisfied-but-optional gaps for confidence."""
        missing = [f for f in spec.requires if not self.has(f)]
        if missing:
            insufficient(
                "tree does not carry required input(s): " + ", ".join(missing)
                + f". {spec.name} needs them to produce a meaningful score; "
                  "returning a zero here would be indistinguishable from a clean result."
            )
        if spec.requires_any and not any(self.has(f) for f in spec.requires_any):
            insufficient(
                "tree carries none of: " + ", ".join(spec.requires_any)
                + f". {spec.name} needs at least one of them; returning a zero here "
                  "would be indistinguishable from a clean result."
            )
        return [f for f in spec.optional if not self.has(f)]

    # -- CFG helpers -----------------------------------------------------
    @staticmethod
    def walk(cfg: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        if not cfg:
            return
        stack = [cfg]
        while stack:
            node = stack.pop()
            yield node
            stack.extend(node.get("children") or [])

    @staticmethod
    def walk_depth(cfg: Dict[str, Any]):
        """Yield (node, nesting_depth). Only NESTING_NODES open a level."""
        if not cfg:
            return
        stack = [(cfg, 0)]
        while stack:
            node, depth = stack.pop()
            yield node, depth
            deeper = depth + 1 if node.get("node_type") in NESTING_NODES else depth
            for child in node.get("children") or []:
                stack.append((child, deeper))

    @staticmethod
    def count(cfg: Dict[str, Any], kinds: Iterable[str]) -> int:
        kinds = set(kinds)
        return sum(1 for n in Tree.walk(cfg) if n.get("node_type") in kinds)

    @staticmethod
    def cyclomatic(cfg: Dict[str, Any]) -> int:
        """1 + decision nodes. Shared so all analyzers agree on the number."""
        return 1 + Tree.count(cfg, DECISION_NODES)

    @staticmethod
    def max_depth(cfg: Dict[str, Any]) -> int:
        return max((d for _, d in Tree.walk_depth(cfg)), default=0)


# ---------------------------------------------------------------------------
# Levels and envelope
# ---------------------------------------------------------------------------

def level_from(score: float, bands: Sequence[float]) -> str:
    """bands = four ascending thresholds; above the last is L5."""
    for i, threshold in enumerate(bands):
        if score <= threshold:
            return f"L{i + 1}"
    return "L5"


def level_from_inverted(score: float, bands: Sequence[float]) -> str:
    """For measures where HIGH is good (maintainability index, comment density)."""
    for i, threshold in enumerate(bands):
        if score >= threshold:
            return f"L{i + 1}"
    return "L5"


def worst(levels: Iterable[str]) -> str:
    ranks = [int(l[1]) for l in levels if isinstance(l, str) and len(l) == 2]
    return f"L{max(ranks)}" if ranks else "L1"


def result(spec: Spec, tree: Tree, *, level: str, score: float, headline: str,
           metrics: Optional[Dict[str, Any]] = None,
           items: Optional[List[Dict[str, Any]]] = None,
           hotspots: Optional[List[Dict[str, Any]]] = None,
           confidence: float = 1.0,
           confidence_reasons: Optional[List[str]] = None,
           extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The uniform output envelope. Every analyzer returns exactly this shape.

    No timestamp: an analyzer's output must be byte-identical for the same tree
    so results can be diffed across runs. The pipeline stamps the run once.
    """
    caps = tree.capabilities()
    used = [f for f in (spec.requires + spec.optional) if caps.get(f)]
    missing = [f for f in spec.optional if not caps.get(f)]

    out: Dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "id": spec.id,
        "sno": spec.sno,
        "complexity": spec.name,
        "tier": spec.tier,
        "analyzer_version": spec.version,
        "language": tree.language,
        "source_file": tree.source_file,
        "status": STATUS_OK,
        "status_reason": None,
        "summary": {"level": level, "score": round(float(score), 2), "headline": headline},
        "metrics": metrics or {},
        "hotspots": hotspots or [],
        "items": items or [],
        "confidence": {
            "score": round(min(max(confidence, 0.0), 1.0), 2),
            "reasons": confidence_reasons or [],
        },
        "inputs_used": used,
        "inputs_missing_optional": missing,
    }
    if extra:
        out.update(extra)
    return out


def insufficient_result(spec: Spec, tree: Tree, reason: str) -> Dict[str, Any]:
    caps = tree.capabilities()
    return {
        "contract_version": CONTRACT_VERSION,
        "id": spec.id,
        "sno": spec.sno,
        "complexity": spec.name,
        "tier": spec.tier,
        "analyzer_version": spec.version,
        "language": tree.language,
        "source_file": tree.source_file,
        "status": STATUS_INSUFFICIENT,
        "status_reason": reason,
        "summary": {"level": None, "score": None,
                    "headline": f"NOT MEASURED - {reason}"},
        "metrics": {},
        "hotspots": [],
        "items": [],
        "confidence": {"score": 0.0, "reasons": ["required input absent"]},
        "inputs_used": [],
        "inputs_missing_required": [f for f in spec.requires if not caps.get(f)],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def normalize(raw: Dict[str, Any], spec: Spec, tree: Tree) -> Dict[str, Any]:
    """Coerce an analyzer's native output into the uniform envelope.

    Analyzers written before this contract return a close-but-not-identical
    shape. Rather than rewrite each one's internals - which risks changing the
    measurements themselves - their output is normalized here. Their metrics,
    items and hotspots pass through untouched; only the envelope fields around
    them are filled in.
    """
    if raw.get("contract_version") == CONTRACT_VERSION:
        return raw                      # already conformant

    caps = tree.capabilities()
    declared = spec.requires + spec.requires_any + spec.optional
    summary = raw.get("summary") or {}

    out: Dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "id": spec.id,
        "sno": spec.sno,
        "complexity": raw.get("complexity", spec.name),
        "tier": spec.tier,
        "analyzer_version": spec.version,
        "language": raw.get("language", tree.language),
        "source_file": tree.source_file,
        "status": STATUS_OK,
        "status_reason": None,
        "summary": {
            "level": summary.get("level"),
            "score": summary.get("score"),
            "headline": summary.get("headline", ""),
        },
        "metrics": raw.get("metrics") or {},
        "hotspots": raw.get("hotspots") or [],
        "items": raw.get("items") or [],
        "confidence": raw.get("confidence") if isinstance(raw.get("confidence"), dict)
        else {"score": 1.0, "reasons": []},
        "inputs_used": [f for f in declared if caps.get(f)],
        "inputs_missing_optional": [f for f in spec.optional if not caps.get(f)],
    }

    # An analyzer that declared it would use an optional input, and did not get
    # it, cannot honestly claim full confidence. Applying this centrally means
    # every analyzer degrades correctly whether or not its author remembered to.
    absent = out["inputs_missing_optional"]
    if absent:
        conf = out["confidence"]
        conf["score"] = round(min(conf.get("score", 1.0), max(0.5, 1.0 - 0.1 * len(absent))), 2)
        reasons = list(conf.get("reasons") or [])
        for f in absent:
            note = f"optional input '{f}' absent from tree"
            if note not in reasons:
                reasons.append(note)
        conf["reasons"] = reasons

    # Preserve any analyzer-specific sections (interpretation, caveats, cycles...).
    for key, value in raw.items():
        if key not in out and key not in ("summary", "metrics", "hotspots", "items"):
            out[key] = value
    return out


def run(analyze: Callable[[Dict[str, Any]], Dict[str, Any]],
        spec: Spec, tree_raw: Dict[str, Any]) -> Dict[str, Any]:
    """Gate on declared inputs, call the analyzer, normalize, map errors.

    The gate runs BEFORE the analyzer, so an analyzer that would have returned
    a misleading zero never gets the chance. This is Rule 4 enforced centrally
    rather than trusted to each author.
    """
    tree = Tree(tree_raw)
    try:
        tree.require(spec)
        return normalize(analyze(tree_raw), spec, tree)
    except InsufficientInput as exc:
        return insufficient_result(spec, tree, str(exc))
    except Exception as exc:  # noqa: BLE001
        out = insufficient_result(spec, tree, f"{type(exc).__name__}: {exc}")
        out["status"] = STATUS_ERROR
        out["summary"]["headline"] = f"ERROR - {type(exc).__name__}: {exc}"
        return out


def cli_main(analyze: Callable[[Dict[str, Any]], Dict[str, Any]], spec: Spec) -> int:
    """Standard entry point. Every analyzer ends with:

        if __name__ == "__main__":
            raise SystemExit(cli_main(analyze, SPEC))

    Reads a tree from a path argument or stdin, writes the envelope to stdout
    or to -o. There is deliberately NO demo fallback: an analyzer run with no
    input must fail visibly, not print sample data that looks like a result.
    """
    args = sys.argv[1:]

    if args and args[0] in ("--spec", "-s"):
        print(json.dumps(spec.as_dict(), indent=2))
        return EXIT_OK

    path: Optional[str] = None
    out_path: Optional[str] = None
    i = 0
    while i < len(args):
        if args[i] in ("-o", "--output") and i + 1 < len(args):
            out_path = args[i + 1]
            i += 2
            continue
        if not args[i].startswith("-"):
            path = args[i]
        i += 1

    if path:
        # utf-8-sig transparently strips a byte-order mark when one is present
        # and behaves exactly like utf-8 when it is not. Windows tooling
        # (Notepad, PowerShell redirection, some exporters) writes BOMs by
        # default, and a plain utf-8 read fails on them with an error that
        # points at "line 1 column 1" rather than at the real cause.
        with open(path, "r", encoding="utf-8-sig") as fh:
            tree_raw = json.load(fh)
    elif not sys.stdin.isatty():
        # Read stdin as BYTES and decode with utf-8-sig. Decoding the text
        # stream instead would apply the console's codepage first, which on
        # Windows turns the BOM into mojibake that no string strip can undo.
        try:
            raw = sys.stdin.buffer.read().decode("utf-8-sig")
        except AttributeError:          # stdin replaced by a text-only object
            raw = sys.stdin.read().lstrip("﻿")
        tree_raw = json.loads(raw)
    else:
        print(
            f"{spec.id}: no input.\n"
            f"  usage: python {spec.sno:02d}_{spec.id}.py TREE.json [-o OUT.json]\n"
            f"         cat TREE.json | python {spec.sno:02d}_{spec.id}.py\n"
            f"         python {spec.sno:02d}_{spec.id}.py --spec\n",
            file=sys.stderr,
        )
        return EXIT_ERROR

    out = run(analyze, spec, tree_raw)
    text = json.dumps(out, indent=2)

    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"{spec.id}: {out['status']} -> {out_path}", file=sys.stderr)
    else:
        print(text)

    return EXIT_OK if out["status"] == STATUS_OK else (
        EXIT_INSUFFICIENT if out["status"] == STATUS_INSUFFICIENT else EXIT_ERROR)
