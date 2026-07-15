from __future__ import annotations

import ast
from pathlib import Path

from migrate_v14_domains import _rewrite_imports


SPECS = (
    (
        "song_agent/domains/quality/release_audio_quality_actions.py",
        "song_agent/domains/quality/release_audio_quality_action_semantics.py",
        "song_agent/domains/quality/release_audio_quality_actions_verifier.py",
        "song_agent.domains.quality.release_audio_quality_actions",
        "song_agent.domains.quality.release_audio_quality_action_semantics",
        {
            "RELEASE_AUDIO_QUALITY_ACTION_QUEUE_PACKAGE_TYPE",
            "RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION",
            "build_expected_action_documents_from_observatory",
        },
    ),
    (
        "song_agent/domains/quality/release_audio_quality_observatory.py",
        "song_agent/domains/quality/release_audio_quality_observatory_semantics.py",
        "song_agent/domains/quality/release_audio_quality_observatory_verifier.py",
        "song_agent.domains.quality.release_audio_quality_observatory",
        "song_agent.domains.quality.release_audio_quality_observatory_semantics",
        {"build_observatory_documents_from_evidence_root"},
    ),
)


def extract(root: Path) -> int:
    for source_name, semantics_name, verifier_name, source_module, semantics_module, roots in SPECS:
        source_path = root / source_name
        semantics_path = root / semantics_name
        verifier_path = root / verifier_name
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
        definitions = _definitions(tree)
        missing_roots = roots - definitions.keys()
        if missing_roots:
            _verify_existing_extraction(
                source_path=source_path,
                semantics_path=semantics_path,
                verifier_path=verifier_path,
                source=source,
                semantics_module=semantics_module,
                roots=roots,
            )
            print(f"already extracted semantics to {semantics_path.name}")
            continue
        selected_names = _definition_closure(definitions, roots)
        selected_nodes = {definitions[name] for name in selected_names}
        if any(isinstance(node, ast.ClassDef) and node.name.endswith("Store") for node in selected_nodes):
            raise ValueError(f"Semantics closure for {source_name} contains a Store")

        imports = [
            ast.get_source_segment(source, node) or ""
            for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        definitions_source = [
            ast.get_source_segment(source, node) or ""
            for node in tree.body
            if node in selected_nodes
        ]
        future = [row for row in imports if row.startswith("from __future__ import")]
        regular = [row for row in imports if row not in future]
        semantics = "\n".join(future) + "\n\n" + "\n".join(regular)
        semantics += "\n\n\n" + "\n\n\n".join(definitions_source) + "\n"
        ast.parse(semantics, filename=str(semantics_path))
        semantics_path.write_text(semantics, encoding="utf-8")

        stripped = _remove_nodes(source, selected_nodes)
        stripped_tree = ast.parse(stripped, filename=str(source_path))
        import_nodes = [
            node
            for node in stripped_tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        insert_at = _node_end_offset(stripped, import_nodes[-1]) if import_nodes else 0
        import_row = f"\nfrom {semantics_module} import {', '.join(sorted(selected_names))}"
        stripped = stripped[:insert_at] + import_row + stripped[insert_at:]
        ast.parse(stripped, filename=str(source_path))
        source_path.write_text(stripped, encoding="utf-8")

        verifier = verifier_path.read_text(encoding="utf-8")
        verifier = _rewrite_imports(verifier, {source_module: semantics_module})
        ast.parse(verifier, filename=str(verifier_path))
        verifier_path.write_text(verifier, encoding="utf-8")
        print(f"extracted {len(selected_names)} definitions to {semantics_path.name}")
    return 0


def _verify_existing_extraction(
    *,
    source_path: Path,
    semantics_path: Path,
    verifier_path: Path,
    source: str,
    semantics_module: str,
    roots: set[str],
) -> None:
    if not semantics_path.is_file():
        raise ValueError(f"Missing semantics module: {semantics_path}")
    semantics = semantics_path.read_text(encoding="utf-8")
    semantics_definitions = _definitions(ast.parse(semantics, filename=str(semantics_path)))
    missing_semantics = roots - semantics_definitions.keys()
    if missing_semantics:
        values = ", ".join(sorted(missing_semantics))
        raise ValueError(f"Missing extracted semantics in {semantics_path}: {values}")

    source_tree = ast.parse(source, filename=str(source_path))
    imported_names = {
        alias.name
        for node in source_tree.body
        if isinstance(node, ast.ImportFrom) and node.module == semantics_module
        for alias in node.names
    }
    missing_imports = roots - imported_names
    if missing_imports:
        values = ", ".join(sorted(missing_imports))
        raise ValueError(f"Missing semantics imports in {source_path}: {values}")

    verifier = verifier_path.read_text(encoding="utf-8")
    verifier_tree = ast.parse(verifier, filename=str(verifier_path))
    if not any(
        isinstance(node, ast.ImportFrom) and node.module == semantics_module
        for node in verifier_tree.body
    ):
        raise ValueError(f"Verifier does not use {semantics_module}: {verifier_path}")


def _definitions(tree: ast.Module) -> dict[str, ast.stmt]:
    result: dict[str, ast.stmt] = {}
    for node in tree.body:
        names: list[str] = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [
                child.id
                for target in targets
                for child in ast.walk(target)
                if isinstance(child, ast.Name)
            ]
        for name in names:
            result[name] = node
    return result


def _definition_closure(
    definitions: dict[str, ast.stmt],
    roots: set[str],
) -> set[str]:
    selected = set(roots)
    pending = list(roots)
    while pending:
        name = pending.pop()
        node = definitions.get(name)
        if node is None:
            raise ValueError(f"Missing semantics root: {name}")
        for child in ast.walk(node):
            if not isinstance(child, ast.Name):
                continue
            if child.id in definitions and child.id not in selected:
                selected.add(child.id)
                pending.append(child.id)
    return selected


def _remove_nodes(source: str, nodes: set[ast.stmt]) -> str:
    result = source
    spans = [
        (
            _node_start_offset(source, node),
            _node_end_offset(source, node),
        )
        for node in nodes
    ]
    for start, end in sorted(spans, reverse=True):
        result = result[:start] + result[end:]
    return result


def _node_start_offset(source: str, node: ast.AST) -> int:
    return _offset(source, int(node.lineno), int(node.col_offset))


def _node_end_offset(source: str, node: ast.AST) -> int:
    return _offset(source, int(node.end_lineno or node.lineno), int(node.end_col_offset or 0))


def _offset(source: str, line: int, column: int) -> int:
    lines = source.splitlines(keepends=True)
    return sum(len(value) for value in lines[: line - 1]) + column


if __name__ == "__main__":
    raise SystemExit(extract(Path.cwd()))
