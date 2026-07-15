from __future__ import annotations

import argparse
import ast
import re
import subprocess
from pathlib import Path


PART_PATTERN = re.compile(r"part_\d+\.py$")
CLASS_PART_PATTERN = re.compile(r"^(?P<prefix>[A-Za-z]+)(?:Routes)?Part\d+$")
PREFIXES = ("handle_", "execute_", "build_", "print_", "run_", "match_")
SUFFIX_PATTERN = re.compile(r"_(route|root|parser|result|report|package)$")
RUNTIME_DEPENDENCY_NAMES = {
    "part_001.py": "core_dependencies",
    "part_002.py": "trust_dependencies",
    "part_003.py": "delivery_quality_dependencies",
    "part_004.py": "program_dependencies",
    "part_005.py": "creation_quality_dependencies",
}
OVERRIDES = {
    "song_agent/interfaces/cli/commands/creation_parts/part_002.py": "program_trust_parser_adapters",
    "song_agent/interfaces/cli/commands/creation_parts/part_003.py": "generation_commands_and_presenter_adapters",
    "song_agent/interfaces/cli/commands/maintenance_parts/part_002.py": "program_parser_adapters",
    "song_agent/interfaces/cli/commands/maintenance_parts/part_003.py": "maintenance_commands_and_presenter_adapters",
    "song_agent/interfaces/cli/commands/program_parts/part_001.py": "program_component_and_cross_domain_adapters",
    "song_agent/interfaces/cli/commands/program_parts/part_002.py": "program_evidence_args_and_adapters",
    "song_agent/interfaces/cli/commands/quality_parts/part_002.py": "audio_lab_parser_and_adapters",
    "song_agent/interfaces/cli/commands/release_check_parts/part_002.py": "program_parser_adapters",
    "song_agent/interfaces/cli/commands/release_check_parts/part_003.py": "release_check_commands_and_presenter_adapters",
    "song_agent/interfaces/cli/commands/trust_parts/part_001.py": "portfolio_parsers_and_cross_domain_adapters",
    "song_agent/interfaces/cli/commands/trust_parts/dependency_parts/part_002.py": "verification_catalog",
    "song_agent/interfaces/cli/commands/trust_parts/part_013.py": "attestation_workflows",
}


def build_rename_map(root: Path) -> dict[Path, Path]:
    mapping: dict[Path, Path] = {}
    used: set[Path] = set()
    for path in sorted((root / "song_agent" / "interfaces").rglob("part_*.py")):
        relative = path.relative_to(root).as_posix()
        stem = OVERRIDES.get(relative) or _semantic_stem(path)
        target = path.with_name(f"{stem}.py")
        if target in used or (target.exists() and target != path):
            stem = f"{stem}_and_{_secondary_stem(path)}"
            target = path.with_name(f"{stem}.py")
        if target in used or (target.exists() and target != path):
            raise ValueError(f"Cannot derive a unique semantic name for {relative}: {target.name}")
        used.add(target)
        mapping[path] = target
    return mapping


def migrate(root: Path) -> dict[str, str]:
    mapping = build_rename_map(root)
    module_mapping = {
        _module_name(root, source): _module_name(root, target)
        for source, target in mapping.items()
    }
    class_mapping = _class_mapping(mapping)
    replacements = _module_replacements(module_mapping)
    for path in sorted((root / "song_agent" / "interfaces").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        updated = source
        for old, new in replacements:
            updated = updated.replace(old, new)
        for old, new in class_mapping.items():
            updated = re.sub(rf"\b{re.escape(old)}\b", new, updated)
        if updated != source:
            ast.parse(updated, filename=str(path))
            path.write_text(updated, encoding="utf-8")
    for source, target in mapping.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
    return {
        source.relative_to(root).as_posix(): target.relative_to(root).as_posix()
        for source, target in mapping.items()
    }


def repair_references(root: Path, revision: str = "HEAD") -> int:
    mapping = _revision_module_mapping(root, revision)
    changed = 0
    for path in sorted((root / "song_agent" / "interfaces").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        updated = _rewrite_relative_imports(root, path, source, mapping)
        if updated == source:
            continue
        ast.parse(updated, filename=str(path))
        path.write_text(updated, encoding="utf-8")
        changed += 1
    return changed


def restore_and_rewrite_aggregators(root: Path, revision: str = "HEAD") -> int:
    mapping = _revision_module_mapping(root, revision)
    class_mapping = _revision_class_mapping(root, revision, mapping)
    output = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=M", revision, "--", "song_agent/interfaces"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    changed = 0
    for relative_text in output.splitlines():
        relative = Path(relative_text)
        source = _git_text(root, revision, relative)
        updated = _rewrite_imports(root, root / relative, source, mapping)
        for old, new in class_mapping.items():
            updated = re.sub(rf"\b{re.escape(old)}\b", new, updated)
        ast.parse(updated, filename=str(relative))
        path = root / relative
        if path.read_text(encoding="utf-8") != updated:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    return changed


def _revision_module_mapping(root: Path, revision: str) -> dict[str, str]:
    output = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", revision, "song_agent/interfaces"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    paths = [Path(line) for line in output.splitlines() if PART_PATTERN.search(line)]
    used: set[Path] = set()
    result: dict[str, str] = {}
    for relative in sorted(paths):
        text = _git_text(root, revision, relative)
        stem = OVERRIDES.get(relative.as_posix()) or _semantic_stem_from_text(relative, text)
        target = relative.with_name(f"{stem}.py")
        if target in used:
            stem = f"{stem}_and_{_secondary_stem_from_text(relative, text)}"
            target = relative.with_name(f"{stem}.py")
        if target in used:
            raise ValueError(f"Cannot recover a unique semantic name for {relative.as_posix()}")
        used.add(target)
        result[_relative_module_name(relative)] = _relative_module_name(target)
    return result


def _revision_class_mapping(
    root: Path,
    revision: str,
    module_mapping: dict[str, str],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for source_module, target_module in module_mapping.items():
        source = Path(*source_module.split(".")).with_suffix(".py")
        target = Path(*target_module.split(".")).with_suffix(".py")
        tree = ast.parse(_git_text(root, revision, source), filename=str(source))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            match = CLASS_PART_PATTERN.fullmatch(node.name)
            if match is None:
                continue
            prefix = match.group("prefix")
            suffix = "".join(part.capitalize() for part in target.stem.split("_"))
            result[node.name] = f"{prefix}{suffix}"
    return result


def _git_text(root: Path, revision: str, relative: Path) -> str:
    return subprocess.run(
        ["git", "show", f"{revision}:{relative.as_posix()}"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _rewrite_relative_imports(
    root: Path,
    path: Path,
    source: str,
    mapping: dict[str, str],
) -> str:
    package = list(path.relative_to(root).with_suffix("").parts[:-1])
    pattern = re.compile(r"^(?P<prefix>\s*from\s+)(?P<dots>\.+)(?P<module>[A-Za-z_][\w.]*)(?P<suffix>\s+import\s+)")
    lines = source.splitlines(keepends=True)
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if match is None:
            continue
        level = len(match.group("dots"))
        keep = len(package) - level + 1
        if keep < 0:
            continue
        anchor = package[:keep]
        absolute = ".".join([*anchor, *match.group("module").split(".")])
        target = mapping.get(absolute)
        if target is None:
            continue
        target_parts = target.split(".")
        if target_parts[: len(anchor)] != anchor:
            raise ValueError(f"Recovered target escapes relative import anchor: {absolute} -> {target}")
        module = ".".join(target_parts[len(anchor) :])
        start, end = match.span("module")
        lines[index] = f"{line[:start]}{module}{line[end:]}"
    return "".join(lines)


def _rewrite_imports(
    root: Path,
    path: Path,
    source: str,
    mapping: dict[str, str],
) -> str:
    package = list(path.relative_to(root).with_suffix("").parts[:-1])
    pattern = re.compile(
        r"^(?P<prefix>\s*from\s+)(?P<dots>\.*)(?P<module>[A-Za-z_][\w.]*)(?P<suffix>\s+import\s+)"
    )
    lines = source.splitlines(keepends=True)
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if match is None:
            continue
        dots = match.group("dots")
        if dots:
            level = len(dots)
            keep = len(package) - level + 1
            if keep < 0:
                continue
            anchor = package[:keep]
            absolute = ".".join([*anchor, *match.group("module").split(".")])
        else:
            anchor = []
            absolute = match.group("module")
        target = mapping.get(absolute)
        if target is None:
            continue
        target_parts = target.split(".")
        if dots:
            if target_parts[: len(anchor)] != anchor:
                raise ValueError(f"Recovered target escapes relative import anchor: {absolute} -> {target}")
            module = ".".join(target_parts[len(anchor) :])
        else:
            module = target
        start, end = match.span("module")
        lines[index] = f"{line[:start]}{module}{line[end:]}"
    return "".join(lines)


def _semantic_stem(path: Path) -> str:
    if path.parent.name == "dependency_parts":
        return "dependency_catalog"
    if path.parent.name == "dependencies":
        return RUNTIME_DEPENDENCY_NAMES.get(path.name, "dependencies")
    return _semantic_stem_from_text(path, path.read_text(encoding="utf-8"))


def _semantic_stem_from_text(path: Path, source: str) -> str:
    if path.parent.name == "dependency_parts":
        return "dependency_catalog"
    if path.parent.name == "dependencies":
        return RUNTIME_DEPENDENCY_NAMES.get(path.name, "dependencies")
    tree = ast.parse(source, filename=str(path))
    definitions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    if definitions and isinstance(definitions[0], ast.ClassDef):
        methods = [
            node.name
            for node in definitions[0].body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name != "__init__"
        ]
        handlers = [name for name in methods if name.startswith("_handle_")]
        return _clean((handlers or methods or [definitions[0].name])[0])
    functions = [node for node in definitions if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    real = [node.name for node in functions if not _resolve_proxy(node)]
    if not real:
        return "cross_domain_adapters" if functions else "dependency_catalog"
    stem = _clean(real[0])
    return f"{stem}_and_adapters" if len(real) < len(functions) else stem


def _secondary_stem(path: Path) -> str:
    return _secondary_stem_from_text(path, path.read_text(encoding="utf-8"))


def _secondary_stem_from_text(path: Path, source: str) -> str:
    tree = ast.parse(source, filename=str(path))
    names = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    return _clean(names[1] if len(names) > 1 else path.parent.name)


def _class_mapping(mapping: dict[Path, Path]) -> dict[str, str]:
    result: dict[str, str] = {}
    for source, target in mapping.items():
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            match = CLASS_PART_PATTERN.fullmatch(node.name)
            if not match:
                continue
            prefix = match.group("prefix")
            suffix = "".join(part.capitalize() for part in target.stem.split("_"))
            result[node.name] = f"{prefix}{suffix}"
    return result


def _module_replacements(mapping: dict[str, str]) -> list[tuple[str, str]]:
    replacements: set[tuple[str, str]] = set(mapping.items())
    for old, new in mapping.items():
        old_parts = old.split(".")
        new_parts = new.split(".")
        for length in range(2, min(len(old_parts), len(new_parts)) + 1):
            if old_parts[-length:-1] == new_parts[-length:-1]:
                replacements.add((".".join(old_parts[-length:]), ".".join(new_parts[-length:])))
    return sorted(replacements, key=lambda row: len(row[0]), reverse=True)


def _module_name(root: Path, path: Path) -> str:
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _relative_module_name(path: Path) -> str:
    parts = list(path.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_proxy(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == "_resolve_symbol"
        for child in ast.walk(node)
    )


def _clean(value: str) -> str:
    result = value.strip("_")
    for prefix in PREFIXES:
        if result.startswith(prefix):
            result = result[len(prefix) :]
            break
    return SUFFIX_PATTERN.sub("", result) or "module"


def main() -> int:
    parser = argparse.ArgumentParser(description="Replace anonymous v13 interface part modules with semantic names.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--repair-references", action="store_true")
    parser.add_argument("--restore-aggregators", action="store_true")
    parser.add_argument("--revision", default="HEAD")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.repair_references:
        changed = repair_references(root, args.revision)
        print(f"repaired interface reference files: {changed}")
        return 0
    if args.restore_aggregators:
        changed = restore_and_rewrite_aggregators(root, args.revision)
        print(f"restored and rewrote interface aggregators: {changed}")
        return 0
    mapping = build_rename_map(root)
    if args.check:
        if mapping:
            for source, target in mapping.items():
                print(f"{source.relative_to(root).as_posix()} -> {target.name}")
            return 1
        print("anonymous interface parts: 0")
        return 0
    result = migrate(root)
    for source, target in result.items():
        print(f"{source} -> {target}")
    print(f"renamed interface parts: {len(result)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
