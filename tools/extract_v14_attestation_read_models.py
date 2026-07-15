from __future__ import annotations

import ast
from pathlib import Path

from extract_v14_trust_verification_contracts import (
    _definitions,
    _definition_closure,
    _import_aliases,
    _node_end_offset,
    _remove_nodes,
    _runtime_names,
    _selected_import_source,
)


SOURCE_MODULE = "song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence"
READ_MODEL_MODULE = "song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence_read_model"
ROOTS = {
    "accepted_evidence_public_summary_from_portfolio_dir",
    "accepted_evidence_verification_summary_from_portfolio_dir",
}


def extract(root: Path) -> int:
    source_path = root.joinpath(*SOURCE_MODULE.split(".")).with_suffix(".py")
    read_model_path = root.joinpath(*READ_MODEL_MODULE.split(".")).with_suffix(".py")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    definitions = _definitions(tree)
    if not ROOTS <= definitions.keys():
        if read_model_path.is_file() and _imports_roots(tree):
            normalized = source.rstrip() + "\n"
            if normalized != source:
                source_path.write_text(normalized, encoding="utf-8")
            print(f"attestation read model already extracted: {read_model_path.name}")
            return 0
        missing = ROOTS - definitions.keys()
        raise ValueError(f"Missing attestation read model roots: {', '.join(sorted(missing))}")

    selected_names = _definition_closure(definitions, ROOTS)
    selected_nodes = {definitions[name] for name in selected_names}
    stores = {
        node.name
        for node in selected_nodes
        if isinstance(node, ast.ClassDef) and node.name.endswith("Store")
    }
    if stores:
        raise ValueError(f"Read model closure contains Store classes: {', '.join(sorted(stores))}")

    imports = _import_aliases(tree)
    referenced_imports: set[str] = set()
    for node in selected_nodes:
        referenced_imports.update(_runtime_names(node) & imports.keys())
    import_source = _selected_import_source(tree, referenced_imports)
    definitions_source = [
        ast.get_source_segment(source, node) or ""
        for node in tree.body
        if node in selected_nodes
    ]
    read_model_source = "from __future__ import annotations\n"
    if import_source:
        read_model_source += "\n" + "\n".join(import_source) + "\n"
    read_model_source += "\n\n" + "\n\n\n".join(definitions_source) + "\n"
    ast.parse(read_model_source, filename=str(read_model_path))

    updated_source = _remove_nodes(source, selected_nodes)
    updated_tree = ast.parse(updated_source, filename=str(source_path))
    import_nodes = [
        node for node in updated_tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    insert_at = _node_end_offset(updated_source, import_nodes[-1]) if import_nodes else 0
    import_row = f"\nfrom {READ_MODEL_MODULE} import {', '.join(sorted(selected_names))}"
    updated_source = updated_source[:insert_at] + import_row + updated_source[insert_at:]
    ast.parse(updated_source, filename=str(source_path))

    read_model_path.write_text(read_model_source, encoding="utf-8")
    source_path.write_text(updated_source.rstrip() + "\n", encoding="utf-8")
    print(f"extracted attestation read model definitions: {len(selected_names)}")
    return 0


def _imports_roots(tree: ast.Module) -> bool:
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == READ_MODEL_MODULE
        for alias in node.names
    }
    return ROOTS <= imported


if __name__ == "__main__":
    raise SystemExit(extract(Path.cwd()))
