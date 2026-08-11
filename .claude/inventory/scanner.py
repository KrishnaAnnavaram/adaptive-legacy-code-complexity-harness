#!/usr/bin/env python3
"""
inventory_agent.py

Scans a Java repository and writes inventory_artifact.json.

Walk -> classify -> register -> extract edges -> detect anomalies -> assemble
one JSON artifact. Everything here is regex/heuristic, deliberately. This is an inventory step,
not a parser: it never builds a symbol table, never resolves method calls, and
never inspects method bodies. Real parsing (AST/ANTLR, full type resolution,
control flow) is the downstream parser agent's job. See
docs/inventory-contract.md for the schema this file promises to produce.

Usage:
    python scanner.py --repo-root <path> [--output-dir <path>] [--exclude-dirs .git,target,build]
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Classification tables
# ---------------------------------------------------------------------------

JAVA_EXTENSIONS = {".java"}
CONFIG_EXTENSIONS = {".xml", ".properties", ".yml", ".yaml"}
SQL_EXTENSIONS = {".sql"}
BUILD_EXTRA_EXTENSIONS = {".gradle", ".kts"}

BUILD_FILENAMES = {
    "pom.xml", "build.gradle", "build.gradle.kts",
    "settings.gradle", "settings.gradle.kts",
}

DEFAULT_EXCLUDE_DIRS = {
    ".git", "target", "build", "out", "bin", "dist",
    ".idea", ".gradle", ".mvn", ".settings", ".vscode", "node_modules",
}

SCAN_EXTENSIONS = JAVA_EXTENSIONS | CONFIG_EXTENSIONS | SQL_EXTENSIONS | BUILD_EXTRA_EXTENSIONS

KIND_MAP = {"class": "class", "interface": "interface", "enum": "enum",
            "record": "record", "@interface": "annotation"}

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

PACKAGE_RE = re.compile(r"\bpackage\s+([\w.]+)\s*;")
IMPORT_RE = re.compile(r"\bimport\s+(static\s+)?([\w.]+(?:\.\*)?)\s*;")

TYPE_DECL_RE = re.compile(
    r"(?:@(?!interface\b)[\w.]+(?:\([^()]*(?:\([^()]*\)[^()]*)*\))?\s*)*"
    r"(?P<mods>(?:public|protected|private|abstract|final|static|sealed|non-sealed|strictfp)\s+)*"
    r"(?P<kind>@interface|\bclass\b|\binterface\b|\benum\b|\brecord\b)\s+"
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"
)

EXTENDS_KEYWORD_RE = re.compile(r"\bextends\b")
IMPLEMENTS_KEYWORD_RE = re.compile(r"\bimplements\b")

LINE_COMMENT_RE = re.compile(r"//[^\n]*")
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
STRING_LITERAL_RE = re.compile(r'"(?:\\.|[^"\\\n])*"')
CHAR_LITERAL_RE = re.compile(r"'(?:\\.|[^'\\\n])*'")


def _blank(match: re.Match) -> str:
    """Replace matched text with spaces, keeping embedded newlines so line
    numbers computed after stripping still line up with the raw source."""
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_noise(raw_text: str) -> str:
    """Blank out comments and string/char literals so regexes below don't
    trip on `// class Foo` in a comment or `"import x;"` in a string."""
    text = BLOCK_COMMENT_RE.sub(_blank, raw_text)
    text = LINE_COMMENT_RE.sub(_blank, text)
    text = STRING_LITERAL_RE.sub(_blank, text)
    text = CHAR_LITERAL_RE.sub(_blank, text)
    return text


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def brace_depths(text: str):
    """depths[i] = brace nesting depth *before* character i. Used to tell a
    top-level type declaration from a nested/inner one without a real parser."""
    depths = [0] * (len(text) + 1)
    d = 0
    for i, ch in enumerate(text):
        depths[i] = d
        if ch == "{":
            d += 1
        elif ch == "}":
            d -= 1
    depths[len(text)] = d
    return depths


def strip_generics(token: str) -> str:
    idx = token.find("<")
    if idx != -1:
        token = token[:idx]
    return token.strip()


def split_top_level_commas(s: str):
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch == "<":
            depth += 1
            cur.append(ch)
        elif ch == ">":
            depth = max(0, depth - 1)
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return parts


def split_types(s: str):
    return [t for t in (strip_generics(p) for p in split_top_level_commas(s)) if t]


def parse_heritage(header: str):
    """Best-effort split of a type header into (extends[], implements[])."""
    ext_m = EXTENDS_KEYWORD_RE.search(header)
    impl_m = IMPLEMENTS_KEYWORD_RE.search(header)

    extends_part = ""
    if ext_m:
        end = impl_m.start() if impl_m and impl_m.start() > ext_m.start() else len(header)
        extends_part = header[ext_m.end():end]

    implements_part = ""
    if impl_m:
        end = ext_m.start() if ext_m and ext_m.start() > impl_m.start() else len(header)
        implements_part = header[impl_m.end():end]

    return split_types(extends_part), split_types(implements_part)


def classify_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in JAVA_EXTENSIONS:
        return "java_source"
    if path.name in BUILD_FILENAMES or ext in BUILD_EXTRA_EXTENSIONS:
        return "build"
    if ext in CONFIG_EXTENSIONS:
        return "config"
    if ext in SQL_EXTENSIONS:
        return "sql"
    return "unknown"


# ---------------------------------------------------------------------------
# Inventory builder
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    severity: str
    type: str
    message: str
    extra: dict = field(default_factory=dict)

    def to_dict(self):
        d = {"severity": self.severity, "type": self.type}
        d.update(self.extra)
        d["message"] = self.message
        return d


class InventoryBuilder:
    def __init__(self, repo_root: Path, exclude_dirs: set):
        self.repo_root = repo_root
        self.exclude_dirs = exclude_dirs

        self.file_registry = []      # one entry per top-level type
        self.build_registry = []
        self.config_registry = []
        self.sql_registry = []

        self.class_lookup = {}       # fqn -> file_registry entry
        self.simple_name_lookup = {} # simple name -> [fqn, ...]

        self.dependency_nodes = []
        self.dependency_edges = []
        self.issues = []

        self.total_files_scanned = 0
        self.java_files_scanned = 0

        # Deferred edge-building state, keyed by file, filled during the
        # registration pass and consumed during the edge pass. Edges cannot
        # be resolved inline while walking: a file processed early can
        # legitimately extend/implement a type declared in a file processed
        # later (alphabetical walk order is not declaration order), so every
        # type in the repo must be registered before any edge is resolved.
        self._pending_edges = []  # list of (entry, type_decl, package, import_by_simple)

    def add_issue(self, severity, type_, message, **extra):
        self.issues.append(Issue(severity, type_, message, extra).to_dict())

    # -- step 1: walk -------------------------------------------------------

    def is_excluded(self, rel_path: Path) -> bool:
        return any(part in self.exclude_dirs for part in rel_path.parts)

    def walk(self):
        for path in sorted(self.repo_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.repo_root)
            if self.is_excluded(rel):
                continue
            if path.suffix.lower() not in SCAN_EXTENSIONS and path.name not in BUILD_FILENAMES:
                continue
            self.total_files_scanned += 1
            self.process_file(path, rel.as_posix())

    def process_file(self, path: Path, rel_path: str):
        file_type = classify_file(path)
        if file_type == "java_source":
            self.java_files_scanned += 1
            self.process_java_file(path, rel_path)
        elif file_type == "build":
            self.build_registry.append({"path": rel_path, "relative_path": rel_path, "type": "build"})
        elif file_type == "config":
            self.config_registry.append({"path": rel_path, "relative_path": rel_path, "type": "config"})
        elif file_type == "sql":
            self.sql_registry.append({"path": rel_path, "relative_path": rel_path, "type": "sql"})
        else:
            self.add_issue("info", "unclassified_extension",
                            f"File extension not recognised: {rel_path}", path=rel_path)

    # -- step 2: per-file type + import extraction ---------------------------

    def process_java_file(self, path: Path, rel_path: str):
        try:
            raw_text = read_text(path)
        except OSError as e:
            self.add_issue("error", "file_read_error", f"Could not read {rel_path}: {e}", path=rel_path)
            return

        text = strip_noise(raw_text)
        loc = raw_text.count("\n") + 1
        size_bytes = path.stat().st_size

        pkg_m = PACKAGE_RE.search(text)
        package = pkg_m.group(1) if pkg_m else ""

        imports = []
        import_by_simple = {}
        for m in IMPORT_RE.finditer(text):
            is_static = bool(m.group(1))
            target = m.group(2)
            imports.append({
                "target": target, "static": is_static, "line": line_of(text, m.start()),
            })
            if not target.endswith(".*"):
                import_by_simple[target.rsplit(".", 1)[-1]] = target

        depths = brace_depths(text)
        type_decls = []
        for m in TYPE_DECL_RE.finditer(text):
            if depths[m.start()] != 0:
                continue  # nested/inner type — out of scope for inventory
            mods = m.group("mods") or ""
            kind = KIND_MAP[m.group("kind")]
            name = m.group("name")
            is_public = "public" in mods.split()
            brace_idx = text.find("{", m.end())
            header_end = brace_idx if brace_idx != -1 else min(len(text), m.end() + 300)
            header = text[m.start():header_end]
            extends_raw, implements_raw = parse_heritage(header)
            type_decls.append({
                "kind": kind, "name": name, "is_public": is_public,
                "line": line_of(text, m.start()),
                "extends_raw": extends_raw, "implements_raw": implements_raw,
            })

        if not type_decls:
            fallback_id = path.stem
            self.add_issue("warning", "no_type_declaration",
                            "No top-level class/interface/enum/record found — file not registered as a type",
                            source_file=rel_path, fallback_id=fallback_id)
            return

        public_types = [t for t in type_decls if t["is_public"]]
        if len(public_types) == 1 and public_types[0]["name"] != path.stem:
            self.add_issue("warning", "public_type_filename_mismatch",
                            f"Public type '{public_types[0]['name']}' does not match filename '{path.stem}'",
                            source_file=rel_path)

        entries = []
        for t in type_decls:
            fqn = f"{package}.{t['name']}" if package else t["name"]
            entry = {
                "id": fqn, "name": t["name"], "package": package, "kind": t["kind"],
                "is_public": t["is_public"], "path": rel_path, "relative_path": rel_path,
                "line": t["line"], "loc": loc, "size_bytes": size_bytes,
                "imports": imports, "extends_raw": t["extends_raw"], "implements_raw": t["implements_raw"],
            }
            if fqn in self.class_lookup:
                other = self.class_lookup[fqn]
                self.add_issue("error", "duplicate_type_id",
                                f"Duplicate type id '{fqn}' across two files",
                                path_a=other["path"], path_b=rel_path)
            else:
                self.class_lookup[fqn] = entry
                self.simple_name_lookup.setdefault(t["name"], []).append(fqn)
            self.file_registry.append(entry)
            entries.append(entry)

        for entry, t in zip(entries, type_decls):
            self._pending_edges.append((entry, t, package, import_by_simple))

    # -- step 3: dependency graph --------------------------------------------

    def resolve_heritage_token(self, token: str, import_by_simple: dict, package: str):
        if "." in token:
            return token, token in self.class_lookup
        if token in import_by_simple:
            fqn = import_by_simple[token]
            return fqn, fqn in self.class_lookup
        same_pkg_fqn = f"{package}.{token}" if package else token
        if same_pkg_fqn in self.class_lookup:
            return same_pkg_fqn, True
        candidates = self.simple_name_lookup.get(token, [])
        if len(candidates) == 1:
            return candidates[0], True
        return token, False

    def resolve_import(self, target: str):
        if target.endswith(".*"):
            prefix = target[:-1]  # keep trailing '.'
            return any(fqn.startswith(prefix) for fqn in self.class_lookup)
        return target in self.class_lookup

    def add_edge(self, source, edge_type, target, line_no, resolved, **extra):
        edge = {"from": source, "to": target, "type": edge_type,
                "resolved": resolved, "source_line_hint": line_no}
        edge.update(extra)
        self.dependency_edges.append(edge)

    def build_edges_for_type(self, entry, type_decl, package, import_by_simple):
        source = entry["id"]

        for imp in entry["imports"]:
            resolved = self.resolve_import(imp["target"])
            edge_type = "IMPORT_STATIC" if imp["static"] else "IMPORT"
            self.add_edge(source, edge_type, imp["target"], imp["line"], resolved)

        for token in type_decl["extends_raw"]:
            target, resolved = self.resolve_heritage_token(token, import_by_simple, package)
            self.add_edge(source, "EXTENDS", target, type_decl["line"], resolved)

        for token in type_decl["implements_raw"]:
            target, resolved = self.resolve_heritage_token(token, import_by_simple, package)
            self.add_edge(source, "IMPLEMENTS", target, type_decl["line"], resolved)

    def resolve_all_edges(self):
        """Second pass: every type in the repo is registered by now, so
        heritage tokens and imports can be resolved against the complete
        class_lookup regardless of which file was walked first."""
        for entry, type_decl, package, import_by_simple in self._pending_edges:
            self.build_edges_for_type(entry, type_decl, package, import_by_simple)

    def build_nodes(self):
        for entry in self.file_registry:
            self.dependency_nodes.append({
                "id": entry["id"], "kind": entry["kind"], "path": entry["path"],
            })

    def detect_inheritance_cycles(self):
        """Real Java can't compile a genuine extends/implements cycle, so a
        cycle found here almost always means the same-name heuristic resolver
        in resolve_heritage_token matched the wrong class. Flagged, not fatal."""
        adjacency = {}
        for edge in self.dependency_edges:
            if edge["type"] in ("EXTENDS", "IMPLEMENTS") and edge["resolved"]:
                adjacency.setdefault(edge["from"], set()).add(edge["to"])

        reported = set()
        for a, targets in adjacency.items():
            for b in targets:
                if a in adjacency.get(b, ()):
                    key = tuple(sorted((a, b)))
                    if key in reported:
                        continue
                    reported.add(key)
                    self.add_issue("warning", "possible_inheritance_cycle",
                                    f"{a} and {b} appear to depend on each other via extends/implements — "
                                    "since valid Java cannot compile a real cycle, this likely means the "
                                    "same-name resolver matched the wrong class; verify manually",
                                    source=a, target=b)

    # -- step 4: stats --------------------------------------------------------

    def compute_stats(self):
        stats = {
            "java_files": self.java_files_scanned,
            "types_total": len(self.file_registry),
            "classes": 0, "interfaces": 0, "enums": 0, "records": 0, "annotations": 0,
            "public_types": 0,
            "packages": len({e["package"] for e in self.file_registry if e["package"]}),
            "build_files": len(self.build_registry),
            "config_files": len(self.config_registry),
            "sql_files": len(self.sql_registry),
            "import_edges_total": 0, "import_edges_resolved": 0, "import_edges_unresolved": 0,
            "extends_edges_total": 0, "extends_edges_resolved": 0,
            "implements_edges_total": 0, "implements_edges_resolved": 0,
        }

        kind_key = {"class": "classes", "interface": "interfaces", "enum": "enums",
                    "record": "records", "annotation": "annotations"}
        for entry in self.file_registry:
            key = kind_key[entry["kind"]]
            if key in stats:
                stats[key] += 1
            if entry["is_public"]:
                stats["public_types"] += 1

        for edge in self.dependency_edges:
            if edge["type"] in ("IMPORT", "IMPORT_STATIC"):
                stats["import_edges_total"] += 1
                stats["import_edges_resolved" if edge["resolved"] else "import_edges_unresolved"] += 1
            elif edge["type"] == "EXTENDS":
                stats["extends_edges_total"] += 1
                if edge["resolved"]:
                    stats["extends_edges_resolved"] += 1
            elif edge["type"] == "IMPLEMENTS":
                stats["implements_edges_total"] += 1
                if edge["resolved"]:
                    stats["implements_edges_resolved"] += 1

        return stats

    # -- step 5: assemble -------------------------------------------------------

    def build(self):
        self.walk()

        if self.java_files_scanned == 0:
            self.add_issue("error", "empty_repository",
                            "File-walker discovered zero .java files. Scan aborted.")
            return {
                "meta": self._meta(),
                "stats": self.compute_stats(),
                "file_registry": [], "build_registry": self.build_registry,
                "config_registry": self.config_registry, "sql_registry": self.sql_registry,
                "dependency_graph": {"nodes": [], "edges": []},
                "issues": self.issues,
            }

        self.resolve_all_edges()
        self.build_nodes()
        self.detect_inheritance_cycles()

        return {
            "meta": self._meta(),
            "stats": self.compute_stats(),
            "file_registry": [self._public_entry(e) for e in self.file_registry],
            "build_registry": self.build_registry,
            "config_registry": self.config_registry,
            "sql_registry": self.sql_registry,
            "dependency_graph": {"nodes": self.dependency_nodes, "edges": self.dependency_edges},
            "issues": self.issues,
        }

    def _meta(self):
        return {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "repo_root": str(self.repo_root),
            "language": "java",
            "agent_version": "0_inventory_java@1.0",
            "total_files_scanned": self.total_files_scanned,
        }

    @staticmethod
    def _public_entry(entry: dict) -> dict:
        # imports/extends_raw/implements_raw are working state consumed into
        # dependency_graph edges already; keep the artifact free of the
        # intermediate fields so downstream consumers see one shape.
        return {k: v for k, v in entry.items()
                if k not in ("imports", "extends_raw", "implements_raw")}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_summary(artifact: dict, output_path: Path):
    stats = artifact["stats"]
    print("=== Inventory Agent Complete ===")
    print(f"Repo scanned : {artifact['meta']['repo_root']}")
    print(f"Java files   : {stats['java_files']}")
    print(f"Types        : {stats['types_total']} "
          f"(classes: {stats['classes']}, interfaces: {stats['interfaces']}, "
          f"enums: {stats['enums']}, records: {stats['records']}, annotations: {stats['annotations']})")
    print(f"Packages     : {stats['packages']}")
    print(f"Build files  : {stats['build_files']}   Config files: {stats['config_files']}   SQL files: {stats['sql_files']}")
    print(f"Imports      : {stats['import_edges_total']} (internal: {stats['import_edges_resolved']}, external: {stats['import_edges_unresolved']})")
    print(f"Extends      : {stats['extends_edges_total']} (resolved: {stats['extends_edges_resolved']})")
    print(f"Implements   : {stats['implements_edges_total']} (resolved: {stats['implements_edges_resolved']})")
    print(f"Issues       : {len(artifact['issues'])}")
    print(f"Output       : {output_path}")
    print("================================")


def main():
    parser = argparse.ArgumentParser(description="Inventory agent for Java repositories.")
    parser.add_argument("--repo-root", required=True, help="Absolute path to root of the Java repository")
    parser.add_argument("-o", "--output-dir", default="./output/inventory", help="Directory to write inventory_artifact.json")
    parser.add_argument("--exclude-dirs", default="", help="Comma-separated extra dirs to skip")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if not repo_root.is_dir():
        print(f"error: REPO_ROOT does not exist or is not a directory: {repo_root}", file=sys.stderr)
        sys.exit(1)

    exclude_dirs = DEFAULT_EXCLUDE_DIRS | {d.strip() for d in args.exclude_dirs.split(",") if d.strip()}

    builder = InventoryBuilder(repo_root, exclude_dirs)
    artifact = builder.build()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "inventory_artifact.json"
    output_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    print_summary(artifact, output_path)

    if artifact["stats"]["java_files"] == 0:
        sys.exit(2)


if __name__ == "__main__":
    main()