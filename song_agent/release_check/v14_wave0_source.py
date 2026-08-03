from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass


SOURCE_EVIDENCE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SourceSpan:
    line: int
    column: int
    end_line: int
    end_column: int

    def identity(self, source_path: str) -> str:
        return f"{source_path}:{self.line}:{self.column}:{self.end_line}:{self.end_column}"

    def document(self) -> dict[str, int]:
        return {"line": self.line, "column": self.column, "end_line": self.end_line, "end_column": self.end_column}


def normalize_source_text(source_text: str) -> str:
    return source_text.replace("\r\n", "\n").replace("\r", "\n")


def source_text_hash(source_text: str) -> str:
    return _sha256(normalize_source_text(source_text))


def source_span(node: ast.AST) -> SourceSpan:
    line = getattr(node, "lineno", None)
    column = getattr(node, "col_offset", None)
    end_line = getattr(node, "end_lineno", None)
    end_column = getattr(node, "end_col_offset", None)
    if (not isinstance(line, int) or not isinstance(column, int)
            or not isinstance(end_line, int) or not isinstance(end_column, int)):
        raise ValueError("Source evidence requires complete AST source coordinates.")
    if (line < 1 or column < 0 or end_line < line or end_column < 0
            or (end_line == line and end_column < column)):
        raise ValueError("Source evidence contains invalid AST source coordinates.")
    return SourceSpan(line, column, end_line, end_column)


def source_fragment(source_text: str, node: ast.AST) -> str:
    normalized = normalize_source_text(source_text)
    span = source_span(node)
    lines = normalized.splitlines(keepends=True)
    if span.end_line > len(lines):
        raise ValueError("Source evidence coordinates exceed the normalized source.")
    start_line = lines[span.line - 1]
    end_line = lines[span.end_line - 1]
    start = _byte_column_to_index(start_line, span.column)
    end = _byte_column_to_index(end_line, span.end_column)
    if span.line == span.end_line:
        return start_line[start:end]
    parts = [start_line[start:], *lines[span.line : span.end_line - 1], end_line[:end]]
    return "".join(parts)


def source_fragment_hash(source_text: str, node: ast.AST) -> str:
    return _sha256(source_fragment(source_text, node))


def source_fragments_hash(source_text: str, nodes: Iterable[ast.AST]) -> str:
    fragments = sorted(source_fragment(source_text, node) for node in nodes)
    payload = json.dumps(fragments, ensure_ascii=False, separators=(",", ":"))
    return _sha256(payload)


def source_site_id(source_path: str, node: ast.AST) -> str:
    return source_span(node).identity(source_path)


def _byte_column_to_index(line: str, byte_column: int) -> int:
    encoded = line.encode("utf-8")
    if byte_column > len(encoded):
        raise ValueError("Source evidence byte column exceeds the source line.")
    try:
        return len(encoded[:byte_column].decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("Source evidence byte column splits a UTF-8 code point.") from exc


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
