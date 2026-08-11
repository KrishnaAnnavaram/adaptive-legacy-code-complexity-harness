"""
parser.py - Java parser for the adaptive legacy code complexity harness.

WHAT THIS IS
------------
The second product-code component, between the inventory scanner and the
complexity agent:

    Java repo --0_inventory--> inventory_artifact.json
                                      |
                                      v   (this script)
                          Normalized Tree (normalized_tree.json)
                                      |
                                      v
                          1_complexity --> complexity_artifact.json

The inventory scanner answers *what types exist and where* (declaration level,
regex, no method bodies). This parser starts where it stops: it reads each
method body and produces the Normalized Tree documented at the top of
`.claude/complexities/_core.py` and in `docs/analyzer-contract.md` - units with
a typed control-flow graph, a resolved call graph, and a type-level dependency
graph.

DESIGN CONSTRAINTS (inherited from the harness - see docs/architecture-decisions.md)
------------------------------------------------------------------------------
* Standard library only. Clients are frequently air-gapped (AD-09). No ANTLR,
  no javalang, no tree-sitter - a hand-written tokenizer and a keyword/brace
  driven statement scanner.
* Heuristic, not authoritative - exactly like the inventory scanner. It handles
  the common Java control constructs and degrades gracefully on the exotic ones
  rather than pretending to be a full JLS-conformant compiler front end. Every
  such limit is listed under "KNOWN LIMITS" below.
* Deterministic. Same repo in, same tree out. Inputs are walked in sorted order;
  no set-iteration order leaks into the output.
* Never fabricate. A method whose body cannot be scanned still produces a unit
  with an empty SEQUENCE cfg and is logged in `issues`, never invented.

CFG node_type vocabulary emitted (subset of _core.py, Java-relevant):
    structure  SEQUENCE BLOCK
    branch     IF ELIF ELSE CASE DEFAULT TERNARY AND OR
    loop       FOR FOREACH WHILE DO_WHILE
    error      CATCH FINALLY RAISE
    jump       RETURN
    effect     CALL

KNOWN LIMITS
------------
* Overload resolution is by name + arity only; two same-arity overloads on one
  type resolve to the first declared. Recorded, not guessed silently.
* Call resolution is best-effort against declared receiver types (this / super /
  fields / params / locals / static TypeName). Calls on expressions whose type
  it cannot infer (chained calls, generics, JDK returns) are left out of the
  call graph rather than pointed at a guess.
* Lambdas and anonymous classes: their bodies are scanned inline into the
  enclosing method's cfg; they are not split into their own units.
* Annotations are skipped as tokens; they do not become nodes.

USAGE
-----
    python .claude/parser/parser.py --inventory out/inventory_artifact.json -o out
    python .claude/parser/parser.py --repo-root path/to/java -o out    # scans directly
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

PARSER_VERSION = "2_parser_java@1.0"

# --------------------------------------------------------------------------- #
# Java keywords we care about (control flow). Everything else is an identifier
# or an operator to the scanner.
# --------------------------------------------------------------------------- #
# NOTE: `record` is deliberately NOT here. It is a *contextual* keyword in Java
# (legal as a method or variable name), so treating it as a hard keyword makes a
# method named `record()` look like a record declaration. Record TYPES are a
# documented limit of this heuristic parser; a method named `record` must still
# parse. Same reasoning keeps `sealed`/`permits`/`yield` out of the hard set.
TYPE_KEYWORDS = {"class", "interface", "enum"}
MODIFIERS = {"public", "private", "protected", "static", "final", "abstract",
             "synchronized", "native", "transient", "volatile", "strictfp",
             "default", "sealed", "non-sealed"}
PRIMITIVES = {"void", "int", "long", "short", "byte", "char", "boolean",
              "float", "double"}
# Keywords that can never be a method name or a type being invoked.
STMT_KEYWORDS = {"if", "else", "for", "while", "do", "switch", "case",
                 "default", "try", "catch", "finally", "return", "throw",
                 "break", "continue", "new", "instanceof", "assert", "yield",
                 "this", "super"}


# =========================================================================== #
# 1. LEXER
# =========================================================================== #
class Tok:
    """A single token with its 1-based source line."""
    __slots__ = ("kind", "text", "line")

    def __init__(self, kind: str, text: str, line: int):
        self.kind = kind        # IDENT KW NUM STR CHAR OP PUNC
        self.text = text
        self.line = line

    def __repr__(self) -> str:  # pragma: no cover - debugging only
        return f"{self.kind}:{self.text!r}@{self.line}"


_MULTI_OPS = ("->", "::", ">>>=", ">>=", "<<=", ">>>", "<<", ">>",
              "<=", ">=", "==", "!=", "&&", "||", "++", "--",
              "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=")


def lex(src: str) -> Tuple[List[Tok], int]:
    """Tokenize Java source. Returns (tokens, comment_line_count).

    Comments and string/char contents are dropped from the token stream but
    their line spans are counted so `comment_lines` stays honest. Line numbers
    are preserved so every unit and node traces back to source.
    """
    toks: List[Tok] = []
    comment_lines = set()
    i, n = 0, len(src)
    line = 1

    def peek(o: int = 0) -> str:
        return src[i + o] if i + o < n else ""

    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r\f":
            i += 1
            continue
        # line comment
        if c == "/" and peek(1) == "/":
            comment_lines.add(line)
            while i < n and src[i] != "\n":
                i += 1
            continue
        # block comment
        if c == "/" and peek(1) == "*":
            comment_lines.add(line)
            i += 2
            while i < n and not (src[i] == "*" and peek(1) == "/"):
                if src[i] == "\n":
                    line += 1
                    comment_lines.add(line)
                i += 1
            i += 2
            continue
        # text block """ ... """
        if c == '"' and peek(1) == '"' and peek(2) == '"':
            start_line = line
            i += 3
            while i < n and not (src[i] == '"' and peek(1) == '"' and peek(2) == '"'):
                if src[i] == "\n":
                    line += 1
                i += 1
            i += 3
            toks.append(Tok("STR", '""', start_line))
            continue
        # string literal
        if c == '"':
            start_line = line
            i += 1
            while i < n and src[i] != '"':
                if src[i] == "\\":
                    i += 1
                elif src[i] == "\n":
                    line += 1
                i += 1
            i += 1
            toks.append(Tok("STR", '""', start_line))
            continue
        # char literal
        if c == "'":
            start_line = line
            i += 1
            while i < n and src[i] != "'":
                if src[i] == "\\":
                    i += 1
                i += 1
            i += 1
            toks.append(Tok("CHAR", "''", start_line))
            continue
        # identifier / keyword
        if c.isalpha() or c == "_" or c == "$":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_$"):
                j += 1
            word = src[i:j]
            toks.append(Tok("KW" if word in _ALL_KW else "IDENT", word, line))
            i = j
            continue
        # number
        if c.isdigit() or (c == "." and peek(1).isdigit()):
            j = i
            while j < n and (src[j].isalnum() or src[j] in "._"):
                j += 1
            toks.append(Tok("NUM", src[i:j], line))
            i = j
            continue
        # multi-char operators
        matched = False
        for op in _MULTI_OPS:
            if src.startswith(op, i):
                toks.append(Tok("OP", op, line))
                i += len(op)
                matched = True
                break
        if matched:
            continue
        # single punctuation / operator
        toks.append(Tok("PUNC" if c in "(){}[];,.@" else "OP", c, line))
        i += 1

    return toks, len(comment_lines)


_ALL_KW = (TYPE_KEYWORDS | MODIFIERS | PRIMITIVES | STMT_KEYWORDS |
           {"package", "import", "extends", "implements", "throws", "void",
            "null", "true", "false", "var"})


# =========================================================================== #
# 2. STRUCTURE PASS - find package, types (incl. nested), members
# =========================================================================== #
class RawType:
    def __init__(self, simple: str, kind: str, line: int):
        self.simple = simple
        self.kind = kind
        self.line = line
        self.extends: List[str] = []
        self.implements: List[str] = []
        self.enclosing: Optional["RawType"] = None
        self.fields: List[str] = []
        self.field_types: Dict[str, str] = {}
        self.methods: List["RawMethod"] = []


class RawMethod:
    def __init__(self, name: str, is_ctor: bool, line: int):
        self.name = name
        self.is_ctor = is_ctor
        self.line = line
        self.end_line = line
        self.params: List[str] = []
        self.param_types: Dict[str, str] = {}
        self.is_static = False
        self.is_public = False
        self.is_abstract = False
        self.body: List[Tok] = []          # tokens strictly inside { }


def _matching_brace(toks: List[Tok], open_idx: int) -> int:
    depth = 0
    for k in range(open_idx, len(toks)):
        t = toks[k]
        if t.kind == "PUNC" and t.text == "{":
            depth += 1
        elif t.kind == "PUNC" and t.text == "}":
            depth -= 1
            if depth == 0:
                return k
    return len(toks) - 1


def _read_type_header(toks: List[Tok], kw_idx: int) -> Tuple[str, List[str], List[str], int]:
    """From a class/interface/enum/record keyword, read name + extends/implements
    up to the opening brace. Returns (simple_name, extends, implements, brace_idx)."""
    k = kw_idx + 1
    name = ""
    while k < len(toks) and not (toks[k].kind == "IDENT"):
        k += 1
    if k < len(toks):
        name = toks[k].text
        k += 1
    extends: List[str] = []
    implements: List[str] = []
    bucket: Optional[List[str]] = None
    depth = 0
    while k < len(toks):
        t = toks[k]
        if t.kind == "PUNC" and t.text == "{" and depth == 0:
            return name, extends, implements, k
        if t.kind == "OP" and t.text in ("<",):
            depth += 1
        elif t.kind == "OP" and t.text in (">",):
            depth = max(0, depth - 1)
        elif depth == 0 and t.kind == "KW" and t.text == "extends":
            bucket = extends
        elif depth == 0 and t.kind == "KW" and t.text == "implements":
            bucket = implements
        elif depth == 0 and t.kind == "IDENT" and bucket is not None:
            # take the simple leading identifier of a (possibly dotted) type
            nxt = toks[k + 1] if k + 1 < len(toks) else None
            if not (nxt and nxt.kind == "PUNC" and nxt.text == "."):
                bucket.append(t.text)
        k += 1
    return name, extends, implements, len(toks) - 1


def structure_pass(toks: List[Tok]) -> Tuple[str, List[RawType]]:
    """Extract the package name and every type (including nested) with members."""
    package = ""
    for idx, t in enumerate(toks):
        if t.kind == "KW" and t.text == "package":
            parts = []
            k = idx + 1
            while k < len(toks) and not (toks[k].kind == "PUNC" and toks[k].text == ";"):
                if toks[k].kind in ("IDENT", "KW"):
                    parts.append(toks[k].text)
                k += 1
            package = ".".join(parts)
            break

    types: List[RawType] = []

    def _match_paren(body: List[Tok], open_idx: int) -> int:
        depth = 0
        for idx in range(open_idx, len(body)):
            if body[idx].kind == "PUNC" and body[idx].text == "(":
                depth += 1
            elif body[idx].kind == "PUNC" and body[idx].text == ")":
                depth -= 1
                if depth == 0:
                    return idx
        return open_idx

    def _skip_annotation(body: List[Tok], k: int) -> int:
        """Skip `@Name` and an optional `(...)` argument list."""
        k += 1                                   # past '@'
        if k < len(body) and body[k].kind in ("IDENT", "KW"):
            k += 1
        if k < len(body) and body[k].kind == "PUNC" and body[k].text == "(":
            k = _match_paren(body, k) + 1
        return k

    def _type_decl_at(body: List[Tok], k: int) -> Optional[int]:
        """If a nested type declaration starts at k (possibly behind modifiers /
        annotations), return the index of its class/interface/enum keyword."""
        j = k
        while j < len(body):
            t = body[j]
            if t.kind == "PUNC" and t.text == "@":
                j = _skip_annotation(body, j)
                continue
            if t.kind == "KW" and t.text in MODIFIERS:
                j += 1
                continue
            break
        if j < len(body) and body[j].kind == "KW" and body[j].text in TYPE_KEYWORDS:
            return j
        return None

    def parse_type_body(body: List[Tok], owner: RawType) -> None:
        """Walk one type body at member depth 0 only. Method bodies are never
        rescanned for members - that is what kept param names and locals from
        being mistaken for fields. Nested types recurse."""
        k = 0
        # enum constants live before the first ';' at depth 0
        if owner.kind == "enum":
            k = _read_enum_constants(body, owner)
        while k < len(body):
            t = body[k]
            if t.kind == "PUNC" and t.text == "@":
                k = _skip_annotation(body, k)
                continue
            if t.kind == "PUNC" and t.text in "{};":
                k += 1
                continue
            decl = _type_decl_at(body, k)
            if decl is not None:
                kw = body[decl]
                name, ext, impl, brace = _read_type_header(body, decl)
                rt = RawType(name, kw.text, kw.line)
                rt.extends, rt.implements, rt.enclosing = ext, impl, owner
                types.append(rt)
                close = _matching_brace(body, brace)
                parse_type_body(body[brace + 1:close], rt)
                k = close + 1
                continue
            nxt = _read_member(body, k, owner)
            k = nxt if (nxt is not None and nxt > k) else k + 1

    def _read_member(body: List[Tok], start: int, owner: RawType) -> Optional[int]:
        """Bound one member at the next depth-0 ';' or '{...}' and classify it."""
        k = start
        depth = 0
        while k < len(body):
            t = body[k]
            if t.kind == "PUNC" and t.text in "([":
                depth += 1
            elif t.kind == "PUNC" and t.text in ")]":
                depth -= 1
            elif depth == 0 and t.kind == "PUNC" and t.text == ";":
                _classify_member(body, start, k, owner, body_open=None, body_close=None)
                return k + 1
            elif depth == 0 and t.kind == "PUNC" and t.text == "{":
                close = _matching_brace(body, k)
                _classify_member(body, start, k, owner, body_open=k, body_close=close)
                return close + 1
            k += 1
        return None

    def _classify_member(body, sig_start, sig_end, owner, body_open, body_close):
        """Decide field vs method/constructor.

        The distinguishing fact is NOT merely 'contains a paren' - a field
        initialised with `new HashMap<>()` contains one too. A method's
        signature paren appears BEFORE any '='; a field's parens live in its
        initialiser, AFTER the '='. So: find the first depth-0 '=' and the first
        depth-0 '('. It is a method only when a '(' precedes any '='.
        """
        sig = body[sig_start:sig_end]
        depth = 0
        eq_idx = None
        paren_idx = None
        for idx, t in enumerate(sig):
            # record first depth-0 '=' / '(' BEFORE the depth counter consumes it
            if depth == 0 and t.kind == "OP" and t.text == "=" and eq_idx is None:
                eq_idx = idx
            if depth == 0 and t.kind == "PUNC" and t.text == "(" and paren_idx is None:
                paren_idx = idx
            if (t.kind == "PUNC" and t.text in "([") or (t.kind == "OP" and t.text == "<"):
                depth += 1
            elif (t.kind == "PUNC" and t.text in ")]") or (t.kind == "OP" and t.text == ">"):
                depth = max(0, depth - 1)

        is_method = paren_idx is not None and (eq_idx is None or paren_idx < eq_idx)
        if is_method:
            name_tok = sig[paren_idx - 1] if paren_idx - 1 >= 0 else None
            if not name_tok or name_tok.kind != "IDENT":
                return
            mods = {t.text for t in sig if t.kind == "KW" and t.text in MODIFIERS}
            name = name_tok.text
            m = RawMethod(name, name == owner.simple, name_tok.line)
            m.is_static = "static" in mods
            m.is_public = "public" in mods
            m.is_abstract = "abstract" in mods or body_open is None
            close_paren = _match_paren(sig, paren_idx)
            _parse_params(sig[paren_idx + 1:close_paren], m)
            if body_open is not None:
                m.body = body[body_open + 1:body_close]
                m.end_line = body[body_close].line if body_close < len(body) else m.line
            owner.methods.append(m)
        else:
            _parse_field(sig, owner)

    def _parse_params(ptoks: List[Tok], m: RawMethod) -> None:
        groups: List[List[Tok]] = [[]]
        depth = 0
        for t in ptoks:
            if t.kind == "OP" and t.text == "<":
                depth += 1
            elif t.kind == "OP" and t.text == ">":
                depth = max(0, depth - 1)
            elif t.kind == "PUNC" and t.text in "([":
                depth += 1
            elif t.kind == "PUNC" and t.text in ")]":
                depth -= 1
            if t.kind == "PUNC" and t.text == "," and depth == 0:
                groups.append([])
            else:
                groups[-1].append(t)
        for g in groups:
            # a param name is the last IDENT; its type is the first type token
            name = next((t.text for t in reversed(g) if t.kind == "IDENT"), None)
            if not name:
                continue
            ptype = None
            for t in g:
                if t.kind == "KW" and t.text in MODIFIERS:
                    continue
                if t.kind == "IDENT" or (t.kind == "KW" and t.text in PRIMITIVES):
                    ptype = t.text
                    break
            m.params.append(name)
            if ptype and ptype != name:
                m.param_types[name] = ptype

    def _parse_field(sig: List[Tok], owner: RawType) -> None:
        """Capture a field's name and declared type. Handles primitive types
        (keyword, not ident) and initialised fields with parens/generics."""
        depth = 0
        eq = len(sig)
        for idx, t in enumerate(sig):
            if t.kind == "PUNC" and t.text in "([{" or (t.kind == "OP" and t.text == "<"):
                depth += 1
            elif t.kind == "PUNC" and t.text in ")]}" or (t.kind == "OP" and t.text == ">"):
                depth = max(0, depth - 1)
            elif depth == 0 and t.kind == "OP" and t.text == "=":
                eq = idx
                break
        head = sig[:eq]
        name = next((t.text for t in reversed(head) if t.kind == "IDENT"), None)
        if not name:
            return
        ftype = None
        for t in head:
            if t.kind == "KW" and t.text in MODIFIERS:
                continue
            if t.kind == "IDENT" or (t.kind == "KW" and t.text in PRIMITIVES):
                ftype = t.text
                break
        if ftype is None or name == ftype:
            return                                # single token: not a real field
        if name not in owner.fields:
            owner.fields.append(name)
            owner.field_types[name] = ftype

    def _read_enum_constants(body: List[Tok], owner: RawType) -> int:
        """Register leading enum constants; return the index past the first ';'."""
        k = 0
        while k < len(body):
            t = body[k]
            if t.kind == "PUNC" and t.text == ";":
                return k + 1
            if t.kind == "PUNC" and t.text == "{":     # constant body -> skip it
                k = _matching_brace(body, k) + 1
                continue
            if t.kind == "IDENT":
                if t.text not in owner.fields:
                    owner.fields.append(t.text)
                k += 1
                if k < len(body) and body[k].kind == "PUNC" and body[k].text == "(":
                    k = _match_paren(body, k) + 1
                continue
            k += 1
        return len(body)

    # top level: find top-level types, then parse each body at member depth
    k = 0
    while k < len(toks):
        t = toks[k]
        if t.kind == "PUNC" and t.text == "@":
            k = _skip_annotation(toks, k)
            continue
        if t.kind == "KW" and t.text in TYPE_KEYWORDS:
            name, ext, impl, brace = _read_type_header(toks, k)
            rt = RawType(name, t.text, t.line)
            rt.extends, rt.implements = ext, impl
            types.append(rt)
            close = _matching_brace(toks, brace)
            parse_type_body(toks[brace + 1:close], rt)
            k = close + 1
            continue
        k += 1

    return package, types


# =========================================================================== #
# 3. CFG BUILDER - turn a method body token list into a control-flow tree
# =========================================================================== #
class CfgBuilder:
    """Recursive-descent over statements, emitting the _core.py node vocabulary."""

    def __init__(self, body: List[Tok]):
        self.t = body
        self.i = 0
        self.n = len(body)

    def build(self) -> Dict[str, Any]:
        children = self._statements(stop={"}"})
        return {"node_type": "SEQUENCE", "children": children}

    # -- token helpers ---------------------------------------------------- #
    def _cur(self) -> Optional[Tok]:
        return self.t[self.i] if self.i < self.n else None

    def _is(self, kind: str, text: Optional[str] = None) -> bool:
        c = self._cur()
        return bool(c and c.kind == kind and (text is None or c.text == text))

    def _skip_parens(self) -> List[Tok]:
        """At a '(', consume the balanced group and return the inner tokens."""
        assert self._is("PUNC", "(")
        depth = 0
        inner: List[Tok] = []
        while self.i < self.n:
            c = self.t[self.i]
            if c.kind == "PUNC" and c.text == "(":
                depth += 1
                if depth == 1:
                    self.i += 1
                    continue
            elif c.kind == "PUNC" and c.text == ")":
                depth -= 1
                if depth == 0:
                    self.i += 1
                    break
            inner.append(c)
            self.i += 1
        return inner

    def _skip_block_or_stmt(self) -> List[Dict[str, Any]]:
        """Parse the block `{...}` or single statement that follows a control head."""
        if self._is("PUNC", "{"):
            self.i += 1
            kids = self._statements(stop={"}"})
            if self._is("PUNC", "}"):
                self.i += 1
            return kids
        return self._statements(stop={";"}, single=True)

    # -- expression scanning (for &&/||/?:/calls inside a condition/expr) --- #
    @staticmethod
    def _expr_nodes(expr: List[Tok], line: int) -> List[Dict[str, Any]]:
        nodes: List[Dict[str, Any]] = []
        k = 0
        while k < len(expr):
            t = expr[k]
            if t.kind == "OP" and t.text == "&&":
                nodes.append({"node_type": "AND", "line": t.line, "children": []})
            elif t.kind == "OP" and t.text == "||":
                nodes.append({"node_type": "OR", "line": t.line, "children": []})
            elif t.kind == "OP" and t.text == "?":
                nodes.append({"node_type": "TERNARY", "line": t.line, "children": []})
            elif (t.kind == "IDENT" and k + 1 < len(expr)
                  and expr[k + 1].kind == "PUNC" and expr[k + 1].text == "("
                  and t.text not in STMT_KEYWORDS):
                nodes.append({"node_type": "CALL", "name": t.text,
                              "line": t.line, "children": []})
            k += 1
        return nodes

    # -- statement list --------------------------------------------------- #
    def _statements(self, stop: set, single: bool = False) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        while self.i < self.n:
            c = self.t[self.i]
            if c.kind == "PUNC" and c.text in stop:
                break
            node = self._statement()
            if node:
                out.extend(node if isinstance(node, list) else [node])
            if single and (self._is("PUNC", ";") or not node):
                if self._is("PUNC", ";"):
                    self.i += 1
                break
        return out

    def _statement(self):
        c = self._cur()
        if c is None:
            return None
        if c.kind == "PUNC" and c.text == "{":
            self.i += 1
            kids = self._statements(stop={"}"})
            if self._is("PUNC", "}"):
                self.i += 1
            return {"node_type": "BLOCK", "line": c.line, "children": kids}
        if c.kind == "PUNC" and c.text == "}":
            return None
        if c.kind == "PUNC" and c.text == ";":
            self.i += 1
            return None
        if c.kind == "KW":
            handler = getattr(self, f"_kw_{c.text}", None)
            if handler:
                return handler()
        # fall through: an expression statement up to ';'
        return self._expr_statement()

    def _expr_statement(self):
        start = self.i
        line = self.t[self.i].line
        depth = 0
        expr: List[Tok] = []
        while self.i < self.n:
            c = self.t[self.i]
            if c.kind == "PUNC" and c.text in "([{":
                depth += 1
            elif c.kind == "PUNC" and c.text in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif c.kind == "PUNC" and c.text == ";" and depth == 0:
                self.i += 1
                break
            expr.append(c)
            self.i += 1
        if self.i == start:
            self.i += 1
            return None
        return self._expr_nodes(expr, line)

    # -- keyword handlers ------------------------------------------------- #
    def _kw_if(self):
        line = self.t[self.i].line
        self.i += 1
        cond = self._skip_parens() if self._is("PUNC", "(") else []
        node = {"node_type": "IF", "line": line,
                "children": self._expr_nodes(cond, line)}
        node["children"].extend(self._skip_block_or_stmt())
        result = [node]
        # else / else-if chain as siblings (flat), matching ELIF semantics
        while self._is("KW", "else"):
            eline = self.t[self.i].line
            self.i += 1
            if self._is("KW", "if"):
                self.i += 1
                econd = self._skip_parens() if self._is("PUNC", "(") else []
                enode = {"node_type": "ELIF", "line": eline,
                         "children": self._expr_nodes(econd, eline)}
                enode["children"].extend(self._skip_block_or_stmt())
                result.append(enode)
            else:
                enode = {"node_type": "ELSE", "line": eline, "children": []}
                enode["children"].extend(self._skip_block_or_stmt())
                result.append(enode)
                break
        return result

    def _kw_for(self):
        line = self.t[self.i].line
        self.i += 1
        header = self._skip_parens() if self._is("PUNC", "(") else []
        is_foreach = any(t.kind == "PUNC" and t.text == ":" for t in header)
        node = {"node_type": "FOREACH" if is_foreach else "FOR", "line": line,
                "children": self._expr_nodes(header, line)}
        node["children"].extend(self._skip_block_or_stmt())
        return node

    def _kw_while(self):
        line = self.t[self.i].line
        self.i += 1
        cond = self._skip_parens() if self._is("PUNC", "(") else []
        node = {"node_type": "WHILE", "line": line,
                "children": self._expr_nodes(cond, line)}
        node["children"].extend(self._skip_block_or_stmt())
        return node

    def _kw_do(self):
        line = self.t[self.i].line
        self.i += 1
        kids = self._skip_block_or_stmt()
        cond: List[Tok] = []
        if self._is("KW", "while"):
            self.i += 1
            if self._is("PUNC", "("):
                cond = self._skip_parens()
        if self._is("PUNC", ";"):
            self.i += 1
        node = {"node_type": "DO_WHILE", "line": line,
                "children": kids + self._expr_nodes(cond, line)}
        return node

    def _kw_switch(self):
        line = self.t[self.i].line
        self.i += 1
        sel = self._skip_parens() if self._is("PUNC", "(") else []
        container = {"node_type": "BLOCK", "line": line, "meta": {"switch": True},
                     "children": self._expr_nodes(sel, line)}
        if not self._is("PUNC", "{"):
            return container
        self.i += 1
        current: Optional[Dict[str, Any]] = None
        while self.i < self.n and not self._is("PUNC", "}"):
            if self._is("KW", "case") or self._is("KW", "default"):
                is_default = self._is("KW", "default")
                cline = self.t[self.i].line
                self.i += 1
                # consume label up to ':' or '->'
                while self.i < self.n and not (
                        self._is("PUNC", ":") or self._is("OP", "->")):
                    self.i += 1
                if self.i < self.n:
                    self.i += 1
                current = {"node_type": "DEFAULT" if is_default else "CASE",
                           "line": cline, "children": []}
                container["children"].append(current)
            else:
                stmt = self._statement()
                if stmt and current is not None:
                    current["children"].extend(
                        stmt if isinstance(stmt, list) else [stmt])
                elif stmt is None:
                    pass
        if self._is("PUNC", "}"):
            self.i += 1
        return container

    def _kw_try(self):
        line = self.t[self.i].line
        self.i += 1
        # optional try-with-resources
        if self._is("PUNC", "("):
            self._skip_parens()
        body = {"node_type": "BLOCK", "line": line, "meta": {"try": True},
                "children": self._skip_block_or_stmt()}
        result = [body]
        while self._is("KW", "catch"):
            cline = self.t[self.i].line
            self.i += 1
            if self._is("PUNC", "("):
                self._skip_parens()
            cnode = {"node_type": "CATCH", "line": cline,
                     "children": self._skip_block_or_stmt()}
            result.append(cnode)
        if self._is("KW", "finally"):
            fline = self.t[self.i].line
            self.i += 1
            fnode = {"node_type": "FINALLY", "line": fline,
                     "children": self._skip_block_or_stmt()}
            result.append(fnode)
        return result

    def _kw_return(self):
        line = self.t[self.i].line
        self.i += 1
        expr: List[Tok] = []
        while self.i < self.n and not self._is("PUNC", ";"):
            expr.append(self.t[self.i])
            self.i += 1
        if self._is("PUNC", ";"):
            self.i += 1
        return {"node_type": "RETURN", "line": line,
                "children": self._expr_nodes(expr, line)}

    def _kw_throw(self):
        line = self.t[self.i].line
        self.i += 1
        expr: List[Tok] = []
        while self.i < self.n and not self._is("PUNC", ";"):
            expr.append(self.t[self.i])
            self.i += 1
        if self._is("PUNC", ";"):
            self.i += 1
        return {"node_type": "RAISE", "line": line,
                "children": self._expr_nodes(expr, line)}

    def _kw_break(self):
        self.i += 1
        while self.i < self.n and not self._is("PUNC", ";"):
            self.i += 1
        if self._is("PUNC", ";"):
            self.i += 1
        return None

    _kw_continue = _kw_break

    def _kw_else(self):
        # stray else (shouldn't happen; if consumes its own else). Skip it.
        self.i += 1
        return None


# =========================================================================== #
# 4. REFERENCE / WRITE / CALL EXTRACTION
# =========================================================================== #
def extract_refs_writes(body: List[Tok], field_names: set) -> Tuple[List[str], List[str]]:
    """references = field identifiers read or written; writes = fields assigned."""
    refs, writes = set(), set()
    for k, t in enumerate(body):
        if t.kind != "IDENT" or t.text not in field_names:
            continue
        # a field mention is a reference
        refs.add(t.text)
        # write if immediately followed by an assignment operator
        nxt = body[k + 1] if k + 1 < len(body) else None
        if nxt and nxt.kind == "OP" and nxt.text in (
                "=", "+=", "-=", "*=", "/=", "%=", "++", "--"):
            writes.add(t.text)
        prv = body[k - 1] if k - 1 >= 0 else None
        if prv and prv.kind == "OP" and prv.text in ("++", "--"):
            writes.add(t.text)
    return sorted(refs), sorted(writes)


def local_var_types(body: List[Tok]) -> Dict[str, str]:
    """Best-effort `Type name` local declarations -> {name: Type}."""
    out: Dict[str, str] = {}
    for k in range(len(body) - 1):
        t, nxt = body[k], body[k + 1]
        if (t.kind == "IDENT" and t.text[:1].isupper()
                and nxt.kind == "IDENT"
                and (k + 2 >= len(body) or body[k + 2].text in ("=", ";", ":", ")"))):
            out[nxt.text] = t.text
    return out


def extract_calls(body: List[Tok], owner_type_id: str, this_type: str,
                  super_type: Optional[str], symbols: Dict[str, str],
                  resolve) -> List[str]:
    """Return resolved callee unit ids reachable from this method body."""
    callees: List[str] = []
    seen = set()
    for k in range(len(body)):
        t = body[k]
        if t.kind == "KW" and t.text == "new":
            # constructor call: new Type(
            j = k + 1
            while j < len(body) and body[j].kind == "IDENT":
                type_name = body[j].text
                if j + 1 < len(body) and body[j + 1].kind == "PUNC" and body[j + 1].text == "(":
                    tid = resolve(type_name, type_name)  # ctor unit id
                    if tid and tid not in seen:
                        seen.add(tid)
                        callees.append(tid)
                    break
                j += 1
            continue
        if t.kind == "IDENT" and k + 1 < len(body) \
                and body[k + 1].kind == "PUNC" and body[k + 1].text == "(" \
                and t.text not in STMT_KEYWORDS:
            method = t.text
            # look back for a receiver:  recv . method (
            recv_type: Optional[str] = this_type
            if k - 2 >= 0 and body[k - 1].kind == "PUNC" and body[k - 1].text == ".":
                recv = body[k - 2]
                if recv.kind == "KW" and recv.text == "this":
                    recv_type = this_type
                elif recv.kind == "KW" and recv.text == "super":
                    recv_type = super_type
                elif recv.kind == "IDENT":
                    recv_type = symbols.get(recv.text, recv.text)
                else:
                    recv_type = None
            uid = resolve(recv_type, method) if recv_type else None
            if uid and uid not in seen:
                seen.add(uid)
                callees.append(uid)
    return callees


# =========================================================================== #
# 5. ASSEMBLY - build the Normalized Tree
# =========================================================================== #
DEFAULT_EXCLUDES = {".git", "target", "build", "out", "bin", "dist", ".idea",
                    ".gradle", ".mvn", ".settings", ".vscode", "node_modules"}


def discover_java_files(repo_root: str, extra_excludes: set) -> List[str]:
    excludes = DEFAULT_EXCLUDES | extra_excludes
    found: List[str] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = sorted(d for d in dirnames if d not in excludes)
        for fn in sorted(filenames):
            if fn.endswith(".java"):
                found.append(os.path.join(dirpath, fn))
    return found


def build_tree(repo_root: str,
               inventory: Optional[Dict[str, Any]],
               extra_excludes: set) -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []
    java_files = discover_java_files(repo_root, extra_excludes)

    # --- pass 1: parse every file into RawTypes -------------------------- #
    file_types: List[Tuple[str, str, List[RawType], int]] = []
    for path in java_files:
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                src = fh.read()
        except OSError as exc:
            issues.append({"severity": "error", "type": "file_read_error",
                           "message": str(exc), "path": path})
            continue
        toks, comment_lines = lex(src)
        package, rtypes = structure_pass(toks)
        rel = os.path.relpath(path, repo_root).replace("\\", "/")
        file_types.append((rel, package, rtypes, src.count("\n") + 1))

    # --- build type id index (fully qualified) --------------------------- #
    def type_id(package: str, rt: RawType) -> str:
        chain = []
        cur: Optional[RawType] = rt
        while cur is not None:
            chain.append(cur.simple)
            cur = cur.enclosing
        chain.reverse()
        base = ".".join(chain[:-1]) if len(chain) > 1 else ""
        outer = chain[0]
        inner = "$".join(chain[1:]) if len(chain) > 1 else ""
        fq = (package + "." if package else "") + outer
        return fq + ("$" + inner if inner else "")

    simple_to_ids: Dict[str, List[str]] = {}
    type_records: List[Tuple[str, str, RawType, str]] = []  # (id, rel, rt, package)
    for rel, package, rtypes, _loc in file_types:
        for rt in rtypes:
            tid = type_id(package, rt)
            type_records.append((tid, rel, rt, package))
            simple_to_ids.setdefault(rt.simple, []).append(tid)

    id_by_simple = {s: ids[0] for s, ids in simple_to_ids.items() if len(ids) == 1}

    def resolve_simple(name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        if name in id_by_simple:
            return id_by_simple[name]
        # already fully-qualified and known?
        return name if any(name == tid for tid, *_ in type_records) else None

    # method index: (type_id, method_name) -> unit id
    method_index: Dict[Tuple[str, str], str] = {}
    for tid, rel, rt, package in type_records:
        for m in rt.methods:
            uid = f"{tid}.{m.name}"
            if (tid, m.name) in method_index:
                continue  # first overload wins (documented limit)
            method_index[(tid, m.name)] = uid

    # inheritance chain for super-call resolution
    parent_of: Dict[str, Optional[str]] = {}
    for tid, rel, rt, package in type_records:
        parent = resolve_simple(rt.extends[0]) if rt.extends else None
        parent_of[tid] = parent

    def resolve_call(recv_type: Optional[str], method: str) -> Optional[str]:
        """recv_type is a simple or fq type name; walk up the chain to find method."""
        tid = resolve_simple(recv_type) or recv_type
        guard = 0
        while tid and guard < 20:
            if (tid, method) in method_index:
                return method_index[(tid, method)]
            tid = parent_of.get(tid)
            guard += 1
        return None

    # --- pass 2: build units + per-type records -------------------------- #
    units: List[Dict[str, Any]] = []
    types_out: List[Dict[str, Any]] = []
    call_edges: List[Dict[str, str]] = []
    call_nodes: List[str] = []

    for tid, rel, rt, package in type_records:
        field_names = set(rt.fields)
        method_uids: List[str] = []
        for m in rt.methods:
            uid = method_index.get((tid, m.name), f"{tid}.{m.name}")
            method_uids.append(uid)
            call_nodes.append(uid)

            cfg = CfgBuilder(m.body).build() if m.body else {
                "node_type": "SEQUENCE", "children": []}
            refs, writes = extract_refs_writes(m.body, field_names)
            symbols = dict(rt.field_types)
            symbols.update(m.param_types)
            symbols.update(local_var_types(m.body))
            super_type = parent_of.get(tid)
            callees = extract_calls(m.body, tid, tid, super_type, symbols, resolve_call)
            for callee in callees:
                if callee != uid or True:  # keep self-recursion edges too
                    call_edges.append({"from": uid, "to": callee})

            loc = max(1, (m.end_line - m.line + 1)) if m.body else 1
            units.append({
                "id": uid,
                "name": m.name,
                "owner_type": tid,
                "loc": loc,
                "start_line": m.line,
                "end_line": m.end_line,
                "params": m.params,
                "references": refs,
                "writes": writes,
                "globals": refs,
                "cfg": cfg,
                "meta": {
                    "static": m.is_static,
                    "exposed": m.is_public,
                    "constructor_params": len(m.params) if m.is_ctor else 0,
                    "constructor": m.is_ctor,
                    "abstract": m.is_abstract,
                },
            })

        types_out.append({
            "id": tid,
            "name": rt.simple,
            "kind": "interface" if rt.kind == "interface"
                    else ("enum" if rt.kind == "enum" else "class"),
            "module": package or rel,
            "fields": rt.fields,
            "methods": method_uids,
            "extends": [x for x in (resolve_simple(e) for e in rt.extends) if x],
            "implements": [x for x in (resolve_simple(i) for i in rt.implements) if x],
        })

    # --- dependency graph (type level, kind-classified) ------------------ #
    dep_nodes = [t["id"] for t in types_out]
    dep_edges: List[Dict[str, str]] = []
    seen_dep = set()

    def add_dep(frm: str, to: str, kind: str):
        key = (frm, to, kind)
        if key not in seen_dep:
            seen_dep.add(key)
            dep_edges.append({"from": frm, "to": to, "kind": kind})

    for t in types_out:
        for parent in t["extends"] + t["implements"]:
            add_dep(t["id"], parent, "internal")

    # imports from the inventory artifact, if provided, classified by target
    if inventory:
        for edge in inventory.get("dependency_graph", {}).get("edges", []):
            if edge.get("type") not in ("IMPORT", "IMPORT_STATIC"):
                continue
            frm = edge.get("from")
            to = edge.get("to", "")
            if edge.get("resolved"):
                add_dep(frm, to, "internal")
            elif to.startswith(("java.sql", "javax.sql")):
                add_dep(frm, to, "db")
                if to not in dep_nodes:
                    dep_nodes.append(to)
            elif to.startswith(("java.", "javax.", "jakarta.")):
                add_dep(frm, to, "library")
                if to not in dep_nodes:
                    dep_nodes.append(to)
            else:
                add_dep(frm, to, "external")
                if to not in dep_nodes:
                    dep_nodes.append(to)

    tree = {
        "language": "java",
        "source_file": repo_root.replace("\\", "/"),
        "units": units,
        "types": types_out,
        "call_graph": {"nodes": sorted(set(call_nodes)), "edges": call_edges},
        "dependency_graph": {"nodes": dep_nodes, "edges": dep_edges},
    }
    return tree, issues, {"java_files": len(java_files), "types": len(types_out),
                          "units": len(units), "call_edges": len(call_edges),
                          "dep_edges": len(dep_edges)}


# =========================================================================== #
# 6. CLI
# =========================================================================== #
def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="Java parser: Normalized Tree builder.")
    ap.add_argument("--inventory", help="Path to inventory_artifact.json (optional).")
    ap.add_argument("--repo-root", help="Java repo root. Defaults to inventory meta.repo_root.")
    ap.add_argument("-o", "--output-dir", default="out", help="Output directory.")
    ap.add_argument("--exclude-dirs", default="", help="Extra comma-separated dirs to skip.")
    args = ap.parse_args(argv)

    inventory = None
    if args.inventory:
        with open(args.inventory, "r", encoding="utf-8-sig") as fh:
            inventory = json.load(fh)

    repo_root = args.repo_root or (inventory or {}).get("meta", {}).get("repo_root")
    if not repo_root or not os.path.isdir(repo_root):
        print(f"parser: repo root not found: {repo_root!r}", file=sys.stderr)
        return 2

    extra = {d.strip() for d in args.exclude_dirs.split(",") if d.strip()}
    tree, issues, stats = build_tree(repo_root, inventory, extra)

    if stats["java_files"] == 0:
        print("parser: no .java files found - not a Java repository?", file=sys.stderr)
        return 2

    os.makedirs(args.output_dir, exist_ok=True)
    out_path = os.path.join(args.output_dir, "normalized_tree.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(tree, fh, indent=2)

    err = sum(1 for i in issues if i["severity"] == "error")
    print("=== Parser Agent Complete ===", file=sys.stderr)
    print(f"Repo parsed  : {repo_root}", file=sys.stderr)
    print(f"Java files   : {stats['java_files']}", file=sys.stderr)
    print(f"Types        : {stats['types']}", file=sys.stderr)
    print(f"Units        : {stats['units']}", file=sys.stderr)
    print(f"Call edges   : {stats['call_edges']}", file=sys.stderr)
    print(f"Dep edges    : {stats['dep_edges']}", file=sys.stderr)
    print(f"Issues       : {len(issues)} ({err} error)", file=sys.stderr)
    print(f"Output       : {out_path}", file=sys.stderr)
    print("=============================", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
