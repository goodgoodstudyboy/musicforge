from __future__ import annotations

import argparse
import ast
from pathlib import Path


ACTIVE_ROOTS = (
    "song_agent/platform",
    "song_agent/application",
    "song_agent/domains",
    "song_agent/capabilities",
    "song_agent/interfaces",
)
ALIAS = "ImplementationDocument"
IMPORT = f"from song_agent.platform.contracts.documents import {ALIAS}"
LEGACY_ANNOTATION = "dict[str, Any]"


def migrate_private_document_types(root: Path, *, write: bool) -> dict[str, object]:
    changed: list[str] = []
    replacement_count = 0
    for relative_root in ACTIVE_ROOTS:
        for path in sorted((root / relative_root).rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            replacements = _private_annotation_replacements(source)
            if not replacements:
                continue
            migrated = _replace_utf8_spans(source, replacements)
            if IMPORT not in migrated:
                migrated = _insert_import(migrated)
            ast.parse(migrated, filename=str(path))
            replacement_count += sum(count for _, _, count in replacements)
            changed.append(path.relative_to(root).as_posix())
            if write:
                path.write_text(migrated, encoding="utf-8")
    return {
        "changed_file_count": len(changed),
        "changed_files": changed,
        "replacement_count": replacement_count,
    }


def _private_annotation_replacements(source: str) -> list[tuple[int, int, int]]:
    tree = ast.parse(source)
    line_offsets = _utf8_line_offsets(source)
    replacements: list[tuple[int, int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("_"):
            continue
        annotations = [node.returns] if node.returns is not None else []
        annotations.extend(
            arg.annotation
            for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
            if arg.annotation is not None
        )
        if node.args.vararg and node.args.vararg.annotation is not None:
            annotations.append(node.args.vararg.annotation)
        if node.args.kwarg and node.args.kwarg.annotation is not None:
            annotations.append(node.args.kwarg.annotation)
        for annotation in annotations:
            segment = ast.get_source_segment(source, annotation) or ""
            count = segment.count(LEGACY_ANNOTATION)
            if not count:
                continue
            start = line_offsets[int(annotation.lineno) - 1] + int(annotation.col_offset)
            end = line_offsets[int(annotation.end_lineno or annotation.lineno) - 1] + int(annotation.end_col_offset or 0)
            replacements.append((start, end, count))
    return replacements


def _replace_utf8_spans(source: str, replacements: list[tuple[int, int, int]]) -> str:
    payload = source.encode("utf-8")
    for start, end, _ in sorted(replacements, reverse=True):
        segment = payload[start:end].decode("utf-8")
        migrated = segment.replace(LEGACY_ANNOTATION, ALIAS).encode("utf-8")
        payload = payload[:start] + migrated + payload[end:]
    return payload.decode("utf-8")


def _utf8_line_offsets(source: str) -> list[int]:
    offsets: list[int] = []
    offset = 0
    for line in source.splitlines(keepends=True):
        offsets.append(offset)
        offset += len(line.encode("utf-8"))
    if not offsets:
        offsets.append(0)
    return offsets


def _insert_import(source: str) -> str:
    lines = source.splitlines()
    index = 0
    if lines and lines[0].startswith("#!"):
        index = 1
    while index < len(lines) and (not lines[index].strip() or lines[index].lstrip().startswith("#")):
        index += 1
    if index < len(lines) and lines[index].startswith("from __future__ import"):
        index += 1
    lines.insert(index, "")
    lines.insert(index + 1, IMPORT)
    return "\n".join(lines) + ("\n" if source.endswith("\n") else "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Name v14 private dynamic-document boundaries.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = migrate_private_document_types(Path(args.repo_root).resolve(), write=args.write)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
