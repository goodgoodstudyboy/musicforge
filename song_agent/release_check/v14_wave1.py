from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources as _resources
from pathlib import Path
from typing import cast

from song_agent.architecture_guardrails import boundary_violations_for_sources, build_architecture_snapshot


SCANNED_ROOTS = ("song_agent/platform", "song_agent/application", "song_agent/interfaces")
COMPOSITION_FILES = frozenset({"song_agent/interfaces/api/server.py"})
COMPOSITION_PREFIXES = ("song_agent/interfaces/bootstrap/",)
COMPOSITION_MAX_LINES, COMPOSITION_MAX_BYTES, COMPOSITION_MAX_AST_NODES = 400, 24_000, 1_200
STRICT_MYPY_MODULES = frozenset({"song_agent.platform.*", "song_agent.application.*", "song_agent.interfaces.*"})
BOOTSTRAP_MYPY_MODULE = "song_agent.interfaces.bootstrap.*"

RESOURCE_ADAPTER_PATH = "song_agent/platform/resource_access.py"
RESOURCE_ADAPTER_MODULE = "song_agent.platform.resource_access"
RESOURCE_ADAPTER_PUBLIC_SYMBOLS = frozenset({"PackagedResource", "read_packaged_text", "read_web_script_text"})
APPROVED_DYNAMIC_IMPORTS = {RESOURCE_ADAPTER_PATH: frozenset({("importlib", "resources")})}
FORBIDDEN_DYNAMIC_MODULES = frozenset({"_frozen_importlib", "_imp", "builtins", "imp", "importlib", "inspect", "pkg_resources", "pkgutil", "pydoc", "runpy", "zipimport"})
FORBIDDEN_DYNAMIC_NAMES = frozenset({"__builtins__", "__import__", "eval", "exec"})
FORBIDDEN_MODULE_REGISTRY_NAMES = frozenset({"__import__", "modules"})
FORBIDDEN_SYS_LOADER_NAMES = frozenset({"meta_path", "modules", "path_hooks", "path_importer_cache"})
FORBIDDEN_LOADER_ATTRIBUTES = FORBIDDEN_SYS_LOADER_NAMES | frozenset(
    {"__loader__", "__spec__", "create_module", "exec_module", "find_module", "find_spec", "load_module"}
)
FORBIDDEN_REFLECTION_ATTRIBUTES = frozenset({"__builtins__", "__closure__", "__code__", "__func__", "__globals__"})
MODULE_HOOK_NAMES = frozenset({"__dir__", "__getattr__"})
REMOVED_CONCRETE_STORE_EXPORTS = frozenset({"song_agent.application.maintenance.LTSMaintenanceStore"})


@dataclass(frozen=True)
class ImportRecord:
    module: str
    symbols: tuple[str, ...]
    line: int
    direct_module_import: bool = False


BOUNDARY_POLICY_RESOURCE = ("v14_wave1_policy.json", "9132844e6e9317e819b5f26c31a173c7ab833ff136be097f5dc69d312b15aa2d")


def _load_boundary_policy() -> dict[str, object]:
    payload = _resources.files("song_agent.release_check").joinpath(BOUNDARY_POLICY_RESOURCE[0]).read_bytes()
    if hashlib.sha256(payload).hexdigest() != BOUNDARY_POLICY_RESOURCE[1]:
        raise RuntimeError("Wave 1 boundary policy hash does not match its approved anchor.")
    document = json.loads(payload)
    if not isinstance(document, dict) or (document.get("schema_version"), document.get("package_type")) != (
        1, "musicforge_v144_wave1_boundary_policy"
    ):
        raise RuntimeError("Wave 1 boundary policy contract is invalid.")
    return cast(dict[str, object], document)


_BOUNDARY_POLICY = _load_boundary_policy()


def _policy_string_map(name: str) -> dict[str, str]:
    return {str(key): str(value) for key, value in cast(dict[str, object], _BOUNDARY_POLICY[name]).items()}


ATTACK_PROBES = tuple(
    (str(row["probe_id"]), str(row["path"]), str(row["source"]), str(row["expected"])) for row in cast(list[dict[str, object]], _BOUNDARY_POLICY["attack_probes"])
)
APPROVED_INTROSPECTION_IMPORTS = {
    str(path): frozenset((str(pair[0]), str(pair[1])) for pair in cast(list[list[object]], pairs))
    for path, pairs in cast(dict[str, object], _BOUNDARY_POLICY["approved_introspection_imports"]).items()
}
APPROVED_DOMAIN_CONTRACTS = {
    str(module): frozenset(str(symbol) for symbol in cast(list[object], symbols))
    for module, symbols in cast(dict[str, object], _BOUNDARY_POLICY["approved_domain_contracts"]).items()
}
CONCRETE_STORE_NAMESPACE_MODULES = frozenset(str(value) for value in cast(list[object], _BOUNDARY_POLICY["concrete_store_namespace_modules"]))
LEGACY_APPLICATION_DOMAIN_DEBT = _policy_string_map("legacy_application_domain_debt")
LEGACY_COMPOSITION_LINE_DEBT = _policy_string_map("legacy_composition_line_debt")
LEGACY_COMPOSITION_SIZE_DEBT = _policy_string_map("legacy_composition_size_debt")
LEGACY_STORE_NAMESPACE_DEBT = _policy_string_map("legacy_store_namespace_debt")
COMPOSITION_MAX_LINE_BYTES = 2_000
FRAME_NAMESPACE_NAMES, RUNTIME_METADATA_NAMES = frozenset({"f_globals", "f_locals"}), frozenset({"__class__", "__module__"})


def evaluate_wave1(root: Path, *, run_mypy: bool = True) -> dict[str, object]:
    sources = collect_wave1_sources(root)
    blockers = inspect_wave1_sources(sources)
    graph_edge_count = 0
    try:
        snapshot = build_architecture_snapshot(root)
        graph_edge_count = len(cast(list[object], snapshot.get("import_pairs", [])))
        blockers.extend(inspect_wave1_dependency_graph(snapshot, sources))
    except (OSError, SyntaxError, ValueError) as exc:
        blockers.append(f"v144_wave1_dependency_graph_unavailable:{type(exc).__name__}")
    blockers.extend(_contract_blockers(root))
    mypy_configuration_blockers = _mypy_configuration_blockers(root)
    blockers.extend(mypy_configuration_blockers)

    probe_results: dict[str, bool] = {}
    for probe_id, path, source, expected in ATTACK_PROBES:
        probe_blockers = inspect_wave1_sources({path: source})
        caught = any(expected in blocker for blocker in probe_blockers)
        probe_results[probe_id] = caught
        if not caught:
            blockers.append(f"v144_wave1_attack_probe_missing:{probe_id}")

    mypy_detail = "not_run"
    if run_mypy and not mypy_configuration_blockers:
        mypy_blockers, mypy_detail = _run_mypy(root)
        blockers.extend(mypy_blockers)
    blockers = sorted(set(blockers))
    return {
        "schema_version": 3,
        "package_type": "musicforge_v144_wave1_verification",
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
        "summary": {
            "source_file_count": len(sources),
            "dependency_graph_edge_count": graph_edge_count,
            "legacy_domain_debt_file_count": _legacy_debt_file_count(sources),
            "interface_domain_import_count": sum("wave1_interface_domain_import" in row for row in blockers),
            "non_composition_store_constructor_count": sum(
                "wave1_application_store_constructor" in row or "wave1_interface_store_constructor" in row for row in blockers
            ),
            "dynamic_forwarding_count": sum("wave1_dynamic_forwarding" in row or "wave1_dynamic_import" in row for row in blockers),
            "attack_probes": probe_results,
            "mypy": mypy_detail,
        },
    }


def run_v144_wave1_platform_application_interfaces_smoke(root: Path) -> tuple[bool, str]:
    report = evaluate_wave1(root)
    return report["status"] == "passed", json.dumps(report, ensure_ascii=False, sort_keys=True)


def collect_wave1_sources(root: Path) -> dict[str, str]:
    sources: dict[str, str] = {}
    for relative_root in SCANNED_ROOTS:
        for path in sorted((root / relative_root).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            sources[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return sources


def inspect_wave1_sources(sources: Mapping[str, str]) -> list[str]:
    blockers: list[str] = []
    valid_sources: dict[str, str] = {}
    for raw_path, source in sorted(sources.items()):
        path = raw_path.replace("\\", "/")
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            blockers.append(f"v144_wave1_syntax:{path}:{exc.lineno or 0}")
            continue
        valid_sources[path] = source
        records = _import_records(tree, path)
        legacy_debt = _legacy_debt_allowed(path, source, records)
        blockers.extend(_import_boundary_blockers(path, records, legacy_debt))
        blockers.extend(_store_construction_blockers(path, tree, legacy_debt))
        blockers.extend(_concrete_store_reference_blockers(path, tree, source, records))
        blockers.extend(_dynamic_capability_blockers(path, tree))
        blockers.extend(_reflection_capability_blockers(path, tree))
        blockers.extend(_module_hook_blockers(path, tree))
        blockers.extend(_static_export_blockers(path, tree))
        if is_composition_path(path):
            source_lines = len(source.splitlines())
            normalized_source = source.replace("\r\n", "\n").replace("\r", "\n")
            source_bytes = len(normalized_source.encode("utf-8"))
            max_line_bytes = max((len(line.encode("utf-8")) for line in normalized_source.splitlines()), default=0)
            ast_nodes = sum(1 for _node in ast.walk(tree))
            oversized = (
                source_lines > COMPOSITION_MAX_LINES
                or source_bytes > COMPOSITION_MAX_BYTES
                or ast_nodes > COMPOSITION_MAX_AST_NODES
            )
            legacy_size_hash = LEGACY_COMPOSITION_SIZE_DEBT.get(path)
            if oversized and legacy_size_hash is not None:
                if _source_hash(source) != legacy_size_hash:
                    blockers.append(f"v144_wave1_composition_size_debt_changed:{path}")
            else:
                if source_lines > COMPOSITION_MAX_LINES:
                    blockers.append(f"v144_wave1_composition_oversized:{path}:{source_lines}")
                if source_bytes > COMPOSITION_MAX_BYTES:
                    blockers.append(f"v144_wave1_composition_oversized_bytes:{path}:{source_bytes}")
                if ast_nodes > COMPOSITION_MAX_AST_NODES:
                    blockers.append(f"v144_wave1_composition_oversized_ast:{path}:{ast_nodes}")
            if max_line_bytes > COMPOSITION_MAX_LINE_BYTES and _source_hash(source) != LEGACY_COMPOSITION_LINE_DEBT.get(path):
                blockers.append(f"v144_wave1_composition_oversized_line:{path}:{max_line_bytes}")
            blockers.extend(_composition_typing_blockers(path, tree))
    blockers.extend(_central_boundary_blockers(boundary_violations_for_sources(valid_sources)))
    return sorted(set(blockers))


def inspect_wave1_dependency_graph(snapshot: Mapping[str, object], _sources: Mapping[str, str]) -> list[str]:
    violations = cast(list[dict[str, object]], snapshot.get("boundary_violations", []))
    return sorted(set(_central_boundary_blockers(violations)))


def _central_boundary_blockers(violations: list[dict[str, object]]) -> list[str]:
    return [f"v144_wave1_dependency_graph_central_boundary:{row.get('reason')}:{row.get('importer')}:{row.get('imported')}" for row in violations]


def is_composition_path(path: str) -> bool:
    return path.replace("\\", "/") in COMPOSITION_FILES or path.replace("\\", "/").startswith(COMPOSITION_PREFIXES)


def _import_boundary_blockers(path: str, records: tuple[ImportRecord, ...], legacy_debt: bool) -> list[str]:
    blockers: list[str] = []
    interface = path.startswith("song_agent/interfaces/")
    application = path.startswith("song_agent/application/")
    composition = is_composition_path(path)
    for record in records:
        if "*" in record.symbols:
            blockers.append(f"v144_wave1_dynamic_forwarding:wildcard_import:{path}:{record.line}")
        if _record_references_prefix(record, (RESOURCE_ADAPTER_MODULE,)):
            valid_adapter_import = (
                record.module == RESOURCE_ADAPTER_MODULE
                and not record.direct_module_import
                and bool(record.symbols)
                and "*" not in record.symbols
                and set(record.symbols).issubset(RESOURCE_ADAPTER_PUBLIC_SYMBOLS)
            )
            if not valid_adapter_import:
                blockers.append(f"v144_wave1_dynamic_import:resource_adapter_private:{path}:{record.line}")
        domain_import = _record_references_prefix(record, ("song_agent.domains",))
        approved_contract = _approved_contract_record(record)
        if application and domain_import and not approved_contract and not legacy_debt:
            blockers.append(f"v144_wave1_application_domain_implementation_import:{path}:{record.line}")
        if interface and not composition and domain_import and not approved_contract:
            blockers.append(f"v144_wave1_interface_domain_import:{path}:{record.line}")
        if (application or (interface and not composition)) and not legacy_debt:
            if any(symbol.endswith("Store") for symbol in record.symbols) and not approved_contract:
                layer = "application" if application else "interface"
                blockers.append(f"v144_wave1_{layer}_concrete_store_import:{path}:{record.line}")
    if application and _has_unapproved_domain_import(records):
        expected = LEGACY_APPLICATION_DOMAIN_DEBT.get(path)
        if expected is not None and not legacy_debt:
            blockers.append(f"v144_wave1_legacy_domain_debt_changed:{path}")
    return blockers


def _store_construction_blockers(path: str, tree: ast.AST, legacy_debt: bool) -> list[str]:
    if legacy_debt or is_composition_path(path):
        return []
    application = path.startswith("song_agent/application/")
    interface = path.startswith("song_agent/interfaces/")
    if not application and not interface:
        return []
    layer = "application" if application else "interface"
    return [
        f"v144_wave1_{layer}_store_constructor:{path}:{node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _expression_name(node.func).endswith("Store")
    ]


def _concrete_store_reference_blockers(
    path: str,
    tree: ast.AST,
    source: str,
    records: tuple[ImportRecord, ...],
) -> list[str]:
    if is_composition_path(path):
        return []
    if not path.startswith(("song_agent/application/", "song_agent/interfaces/")):
        return []
    bindings = _import_symbol_bindings(tree, path)
    blockers: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        identity = _qualified_expression(node, bindings)
        if identity in REMOVED_CONCRETE_STORE_EXPORTS:
            blockers.append(f"v144_wave1_concrete_store_reference:{path}:{node.lineno}:{identity}")
    namespace_imports = [record for record in records if _imports_store_namespace(record)]
    if namespace_imports and _source_hash(source) != LEGACY_STORE_NAMESPACE_DEBT.get(path):
        blockers.extend(
            f"v144_wave1_concrete_store_namespace_import:{path}:{record.line}:{record.module}"
            for record in namespace_imports
        )
    return blockers


def _dynamic_capability_blockers(path: str, tree: ast.AST) -> list[str]:
    blockers: list[str] = []
    bindings = _import_symbol_bindings(tree, path)
    sys_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in FORBIDDEN_DYNAMIC_MODULES:
                    blockers.append(f"v144_wave1_dynamic_import:forbidden_module:{path}:{node.lineno}:{root}")
                if alias.name == "sys":
                    sys_aliases.add(alias.asname or "sys")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            requested = {(module, alias.name) for alias in node.names}
            if root in FORBIDDEN_DYNAMIC_MODULES and not requested.issubset(_approved_dynamic_imports(path)):
                blockers.append(f"v144_wave1_dynamic_import:forbidden_module:{path}:{node.lineno}:{root}")
            if module == "sys":
                for alias in node.names:
                    if alias.name in FORBIDDEN_SYS_LOADER_NAMES:
                        kind = "sys_modules" if alias.name == "modules" else "sys_loader"
                        blockers.append(f"v144_wave1_dynamic_import:{kind}:{path}:{node.lineno}:{alias.name}")
        if isinstance(node, ast.Call):
            function_identity = _qualified_expression(node.func, bindings)
            if isinstance(node.func, ast.Name) and (
                node.func.id in {"globals", "locals"} or (node.func.id == "vars" and not node.args and not node.keywords)
            ):
                blockers.append(f"v144_wave1_dynamic_forwarding:module_namespace_access:{path}:{node.lineno}")
            if function_identity in {"sys._getframe", "inspect.currentframe"}:
                blockers.append(f"v144_wave1_dynamic_import:module_registry:{path}:{node.lineno}")
            if isinstance(node.func, ast.Name) and node.func.id == "vars" and node.args:
                target_identity = _qualified_expression(node.args[0], bindings)
                if target_identity in {"sys", "inspect"}:
                    blockers.append(f"v144_wave1_dynamic_import:module_registry:{path}:{node.lineno}")
            if isinstance(node.func, ast.Name) and node.func.id == "getattr" and node.args:
                target_identity = _qualified_expression(node.args[0], bindings)
                if target_identity in {"sys", "inspect"}:
                    blockers.append(f"v144_wave1_dynamic_import:module_registry:{path}:{node.lineno}")
            if isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) > 1 and _constant_string(node.args[1]) in FORBIDDEN_LOADER_ATTRIBUTES:
                blockers.append(f"v144_wave1_dynamic_import:module_registry:{path}:{node.lineno}")
            if _runtime_metadata_mutation(node):
                blockers.append(f"v144_wave1_dynamic_forwarding:runtime_metadata:{path}:{node.lineno}")
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in {"globals", "locals"}:
            blockers.append(f"v144_wave1_dynamic_forwarding:module_namespace_access:{path}:{node.lineno}")
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in FORBIDDEN_DYNAMIC_NAMES:
            blockers.append(f"v144_wave1_dynamic_import:builtin:{path}:{node.lineno}")
        if isinstance(node, ast.Attribute):
            identity = _qualified_expression(node, bindings)
            if node.attr in FORBIDDEN_DYNAMIC_NAMES or node.attr in FORBIDDEN_MODULE_REGISTRY_NAMES:
                blockers.append(f"v144_wave1_dynamic_import:builtin:{path}:{node.lineno}")
            if node.attr in FORBIDDEN_SYS_LOADER_NAMES and isinstance(node.value, ast.Name) and node.value.id in sys_aliases:
                kind = "sys_modules" if node.attr == "modules" else "sys_loader"
                blockers.append(f"v144_wave1_dynamic_import:{kind}:{path}:{node.lineno}:{node.attr}")
            elif node.attr in FORBIDDEN_LOADER_ATTRIBUTES:
                blockers.append(f"v144_wave1_dynamic_import:loader_protocol:{path}:{node.lineno}:{node.attr}")
            if identity in {"sys.__dict__", "sys._getframe", "inspect.currentframe"} or node.attr in FRAME_NAMESPACE_NAMES:
                blockers.append(f"v144_wave1_dynamic_import:module_registry:{path}:{node.lineno}")
        if isinstance(node, ast.Subscript) and _constant_string(node.slice) in FORBIDDEN_LOADER_ATTRIBUTES:
            blockers.append(f"v144_wave1_dynamic_import:module_registry:{path}:{node.lineno}")
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(_writes_runtime_metadata(target) for target in targets):
                blockers.append(f"v144_wave1_dynamic_forwarding:runtime_metadata:{path}:{node.lineno}")
        if isinstance(node, ast.ClassDef) and _module_type_rewriter(node, bindings):
            blockers.append(f"v144_wave1_dynamic_forwarding:module_type_setattr:{path}:{node.lineno}")
    return blockers


def _reflection_capability_blockers(path: str, tree: ast.AST) -> list[str]:
    blockers: set[str] = set()
    string_bindings = _static_string_bindings(tree)
    for node in ast.walk(tree):
        value = node.attr if isinstance(node, ast.Attribute) else _constant_string(node, string_bindings)
        if value in FORBIDDEN_REFLECTION_ATTRIBUTES:
            blockers.add(f"v144_wave1_dynamic_reflection:callable_namespace:{path}:{getattr(node, 'lineno', 0)}:{value}")
    return sorted(blockers)


def _module_hook_blockers(path: str, tree: ast.Module) -> list[str]:
    blockers: list[str] = []
    string_bindings = _static_string_bindings(tree)
    scoped_nodes = {
        child
        for scope in ast.walk(tree) if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)) for child in ast.walk(scope) if child is not scope
    }
    for node in ast.walk(tree):
        names: set[str] = set()
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            names.update(node.names)
        elif node not in scoped_nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names.add(node.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        value = _constant_string(node, string_bindings)
        if value:
            names.add(value)
        blockers.extend(f"v144_wave1_dynamic_forwarding:module_hook:{path}:{getattr(node, 'lineno', 0)}:{name}" for name in names & MODULE_HOOK_NAMES)
    return blockers


def _static_export_blockers(path: str, tree: ast.Module) -> list[str]:
    blockers: list[str] = []
    assignments = [
        node for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(_targets_name(target, "__all__") for target in (node.targets if isinstance(node, ast.Assign) else [node.target]))
    ]
    approved_nodes = {id(node) for node in assignments}
    if len(assignments) > 1:
        blockers.append(f"v144_wave1_dynamic_forwarding:dynamic_all:{path}:multiple")
    for node in assignments:
        if node.value is None or not _static_string_sequence(node.value):
            blockers.append(f"v144_wave1_dynamic_forwarding:dynamic_all:{path}:{node.lineno}")
    for item in ast.walk(tree):
        if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load) and item.id == "__all__":
            blockers.append(f"v144_wave1_dynamic_forwarding:dynamic_all:{path}:{item.lineno}")
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute):
            if isinstance(item.func.value, ast.Name) and item.func.value.id == "__all__":
                blockers.append(f"v144_wave1_dynamic_forwarding:dynamic_all:{path}:{item.lineno}")
        if isinstance(item, (ast.Assign, ast.AnnAssign, ast.AugAssign)) and id(item) not in approved_nodes:
            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
            if any(_targets_name(target, "__all__") for target in targets):
                blockers.append(f"v144_wave1_dynamic_forwarding:dynamic_all:{path}:{item.lineno}")
    return blockers


def _composition_typing_blockers(path: str, tree: ast.AST) -> list[str]:
    unsafe_aliases = _unsafe_type_aliases(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Lambda):
            return [f"v144_wave1_untyped_composition_factory:{path}"]
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        variadic = [argument for argument in (node.args.vararg, node.args.kwarg) if argument]
        if any(argument.arg not in {"self", "cls"} and argument.annotation is None for argument in arguments):
            return [f"v144_wave1_untyped_composition_factory:{path}"]
        factory_like = node.name == "factory" or node.name.startswith(("build", "compose", "create", "make", "provide"))
        if factory_like and any(
            argument.arg not in {"self", "cls"}
            and argument.annotation is not None
            and _unsafe_boundary_annotation(argument.annotation, unsafe_aliases)
            for argument in arguments
        ):
            return [f"v144_wave1_untyped_composition_factory:{path}"]
        if any(
            argument.annotation is None or _unsafe_boundary_annotation(argument.annotation, unsafe_aliases)
            for argument in variadic
        ):
            return [f"v144_wave1_untyped_composition_factory:{path}"]
        if node.returns is None or _unsafe_return_annotation(node.returns, unsafe_aliases):
            return [f"v144_wave1_untyped_composition_factory:{path}"]
    return []


def _contract_blockers(root: Path) -> list[str]:
    blockers: list[str] = []
    document_path = root / "song_agent" / "platform" / "contracts" / "documents.py"
    if not document_path.is_file():
        return ["v144_wave1_json_contract_missing"]
    tree = ast.parse(document_path.read_text(encoding="utf-8"), filename=str(document_path))
    assignments = {node.target.id for node in tree.body if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)}
    functions = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for name in ("JsonPrimitive", "JsonValue", "JsonDocument"):
        if name not in assignments:
            blockers.append(f"v144_wave1_json_contract_symbol:{name}")
    for name in ("is_json_value", "is_json_document", "normalize_json_value", "normalize_json_document"):
        if name not in functions:
            blockers.append(f"v144_wave1_json_contract_parser:{name}")
    service_path = root / "song_agent" / "application" / "program" / "service.py"
    if not service_path.is_file():
        blockers.append("v144_wave1_program_use_case_missing")
    else:
        service_tree = ast.parse(service_path.read_text(encoding="utf-8"), filename=str(service_path))
        methods = {node.name for node in ast.walk(service_tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name in ("list_programs", "create_program", "get_program"):
            if name not in methods:
                blockers.append(f"v144_wave1_program_use_case:{name}")
        if any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr" for node in ast.walk(service_tree)
        ):
            blockers.append("v144_wave1_program_dynamic_dispatch")
    maintenance_path = root / "song_agent" / "application" / "maintenance.py"
    if not maintenance_path.is_file():
        blockers.append("v144_wave1_maintenance_executor_injection")
    else:
        maintenance_source = maintenance_path.read_text(encoding="utf-8")
        maintenance_tree = ast.parse(maintenance_source, filename=str(maintenance_path))
        maintenance_classes = {node.name for node in maintenance_tree.body if isinstance(node, ast.ClassDef)}
        maintenance_imports = _import_records(
            maintenance_tree,
            "song_agent/application/maintenance.py",
        )
        if "release_check_executor" not in maintenance_source:
            blockers.append("v144_wave1_maintenance_executor_injection")
        if "MaintenanceStorePort" not in maintenance_classes:
            blockers.append("v144_wave1_maintenance_store_port_missing")
        if any(symbol.endswith("Store") for record in maintenance_imports for symbol in record.symbols):
            blockers.append("v144_wave1_maintenance_concrete_store_export")
    generation_path = root / "song_agent" / "application" / "generation" / "service.py"
    if not generation_path.is_file() or "node_store_factory" not in generation_path.read_text(encoding="utf-8"):
        blockers.append("v144_wave1_generation_store_injection")
    capability_modules = {
        "program_verifier_capabilities.py": ("ACTIVE_VERIFIER_CAPABILITIES", "active_verifier_registry"),
        "program_lifecycle_capabilities.py": ("ACTIVE_LIFECYCLE_CAPABILITIES", "active_lifecycle_registry"),
    }
    capability_root = root / "song_agent" / "interfaces" / "bootstrap" / "api"
    for filename, required_symbols in capability_modules.items():
        path = capability_root / filename
        if not path.is_file():
            blockers.append(f"v144_wave1_program_capability_module_missing:{filename}")
            continue
        module_tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        defined = {
            target.id
            for node in module_tree.body
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
            if isinstance(target, ast.Name)
        }
        missing = set(required_symbols) - defined
        blockers.extend(f"v144_wave1_program_capability_symbol_missing:{filename}:{symbol}" for symbol in sorted(missing))
    return blockers


def _mypy_configuration_blockers(root: Path) -> list[str]:
    path = root / "pyproject.toml"
    if not path.is_file():
        return ["v144_wave1_mypy_config_missing"]
    with path.open("rb") as handle:
        document = tomllib.load(handle)
    tool = document.get("tool")
    mypy = tool.get("mypy") if isinstance(tool, dict) else None
    if not isinstance(mypy, dict):
        return ["v144_wave1_mypy_config_missing"]
    overrides = mypy.get("overrides")
    strict_modules: set[str] = set()
    bootstrap_strict = False
    for row in overrides if isinstance(overrides, list) else []:
        if not isinstance(row, dict):
            continue
        modules_value = row.get("module")
        modules = ({modules_value} if isinstance(modules_value, str) else {str(value) for value in modules_value} if isinstance(modules_value, list) else set())
        explicit_any = row.get("disallow_any_explicit") is True
        if explicit_any:
            strict_modules.update(modules)
        if BOOTSTRAP_MYPY_MODULE in modules:
            bootstrap_strict = explicit_any and row.get("disallow_untyped_defs") is True and row.get("disallow_incomplete_defs") is True
    blockers = [f"v144_wave1_mypy_disallow_any_missing:{module}" for module in sorted(STRICT_MYPY_MODULES - strict_modules)]
    if not bootstrap_strict:
        blockers.append("v144_wave1_mypy_bootstrap_strict_missing")
    return blockers


def _run_mypy(root: Path) -> tuple[list[str], str]:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "mypy", "--no-incremental"], cwd=root, capture_output=True, text=True, timeout=300, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ["v144_wave1_mypy_unavailable"], str(exc)
    output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    detail = output.splitlines()[-1] if output else f"exit={completed.returncode}"
    return ([] if completed.returncode == 0 else ["v144_wave1_mypy_failed"]), detail


def _import_records(tree: ast.AST, path: str) -> tuple[ImportRecord, ...]:
    records: list[ImportRecord] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            records.extend(ImportRecord(alias.name, (), node.lineno, direct_module_import=True) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            records.append(ImportRecord(_absolute_import_from(node, path), tuple(alias.name for alias in node.names), node.lineno))
    return tuple(records)


def _absolute_import_from(node: ast.ImportFrom, path: str) -> str:
    if node.level == 0:
        return node.module or ""
    parts = path.replace("\\", "/").removesuffix(".py").split("/")
    package = parts[:-1]
    keep = max(0, len(package) - node.level + 1)
    suffix = (node.module or "").split(".") if node.module else []
    return ".".join([*package[:keep], *suffix])


def _approved_contract_record(record: ImportRecord) -> bool:
    allowed = APPROVED_DOMAIN_CONTRACTS.get(record.module)
    return allowed is not None and not record.direct_module_import and bool(record.symbols) and "*" not in record.symbols and set(record.symbols).issubset(allowed)


def _has_unapproved_domain_import(records: tuple[ImportRecord, ...]) -> bool:
    return any(_record_references_prefix(record, ("song_agent.domains",)) and not _approved_contract_record(record) for record in records)


def _legacy_debt_allowed(path: str, source: str, records: tuple[ImportRecord, ...]) -> bool:
    return _has_unapproved_domain_import(records) and _source_hash(source) == LEGACY_APPLICATION_DOMAIN_DEBT.get(path)


def _legacy_debt_file_count(sources: Mapping[str, str]) -> int:
    count = 0
    for path, source in sources.items():
        if not path.startswith("song_agent/application/"):
            continue
        try:
            records = _import_records(ast.parse(source), path)
        except SyntaxError:
            continue
        if _legacy_debt_allowed(path, source, records):
            count += 1
    return count


def _source_hash(source: str) -> str:
    return hashlib.sha256(source.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")).hexdigest()


def _matches_prefix(value: str, prefixes: tuple[str, ...]) -> bool:
    return any(value == prefix or value.startswith(prefix + ".") for prefix in prefixes)


def _record_references_prefix(record: ImportRecord, prefixes: tuple[str, ...]) -> bool:
    return _matches_prefix(record.module, prefixes) or any(_matches_prefix(f"{record.module}.{symbol}" if record.module else symbol, prefixes) for symbol in record.symbols)


def _import_symbol_bindings(tree: ast.AST, path: str) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".", 1)[0]
                bindings[local] = alias.name if alias.asname else local
        elif isinstance(node, ast.ImportFrom):
            module = _absolute_import_from(node, path)
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                bindings[local] = f"{module}.{alias.name}" if module else alias.name
    return bindings


def _qualified_expression(node: ast.AST, bindings: Mapping[str, str]) -> str:
    if isinstance(node, ast.Name):
        return bindings.get(node.id, "")
    if isinstance(node, ast.Attribute):
        parent = _qualified_expression(node.value, bindings)
        return f"{parent}.{node.attr}" if parent else ""
    return ""


def _expression_name(node: ast.AST) -> str:
    return node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else ""


def _constant_string(node: ast.AST, bindings: Mapping[str, str] | None = None) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and bindings is not None:
        return bindings.get(node.id, "")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _constant_string(node.left, bindings), _constant_string(node.right, bindings)
        return left + right if left and right else ""
    if isinstance(node, ast.JoinedStr):
        parts = [item.value for item in node.values if isinstance(item, ast.Constant) and isinstance(item.value, str)]
        return "".join(parts) if len(parts) == len(node.values) else ""
    return ""


def _static_string_bindings(tree: ast.AST) -> dict[str, str]:
    bindings: dict[str, str] = {}
    while True:
        before = len(bindings)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
                targets, value = [node.target], node.value
            else:
                continue
            names = {
                item.id
                for target in targets
                for item in ast.walk(target)
                if isinstance(item, ast.Name)
            }
            resolved = _constant_string(value, bindings)
            if resolved:
                bindings.update((name, resolved) for name in names)
        if before == len(bindings):
            return bindings


def _module_type_rewriter(node: ast.ClassDef, bindings: Mapping[str, str]) -> bool:
    methods = {item.name for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
    module_type_base = any(
        _expression_name(base) == "ModuleType" or _qualified_expression(base, bindings) == "types.ModuleType"
        for base in node.bases
    )
    return module_type_base and "__setattr__" in methods


def _writes_runtime_metadata(node: ast.AST) -> bool:
    if isinstance(node, ast.Attribute):
        return node.attr in {"__class__", "__module__"}
    if isinstance(node, ast.Subscript):
        return _constant_string(node.slice) in RUNTIME_METADATA_NAMES or _writes_runtime_metadata(node.value)
    if isinstance(node, (ast.Tuple, ast.List)):
        return any(_writes_runtime_metadata(item) for item in node.elts)
    return False


def _static_string_sequence(node: ast.AST) -> bool:
    return isinstance(node, (ast.List, ast.Tuple)) and all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in node.elts)


def _targets_name(node: ast.AST, name: str) -> bool:
    if isinstance(node, ast.Name):
        return node.id == name
    if isinstance(node, (ast.Tuple, ast.List)):
        return any(_targets_name(item, name) for item in node.elts)
    if isinstance(node, (ast.Attribute, ast.Subscript)):
        return _targets_name(node.value, name)
    return False


def _unsafe_boundary_annotation(annotation: ast.expr, aliases: frozenset[str] = frozenset()) -> bool:
    parsed = _parsed_annotation(annotation)
    return any(
        isinstance(node, ast.Name) and node.id in {"Any", "object", *aliases}
        or isinstance(node, ast.Attribute) and node.attr in {"Any", "object"}
        for node in ast.walk(parsed)
    )


def _unsafe_return_annotation(annotation: ast.expr, aliases: frozenset[str]) -> bool:
    parsed = _parsed_annotation(annotation)
    if any(
        isinstance(node, (ast.Name, ast.Attribute)) and _expression_name(node) == "Any"
        for node in ast.walk(parsed)
    ):
        return True
    if isinstance(parsed, (ast.Name, ast.Attribute)):
        return _expression_name(parsed) in {"object", *aliases}
    if isinstance(parsed, ast.BinOp) and isinstance(parsed.op, ast.BitOr):
        return _unsafe_return_annotation(parsed.left, aliases) or _unsafe_return_annotation(parsed.right, aliases)
    if isinstance(parsed, ast.Subscript) and _expression_name(parsed.value) in {"Optional", "Union"}:
        return _unsafe_boundary_annotation(parsed.slice, aliases)
    return False


def _unsafe_type_aliases(tree: ast.AST) -> frozenset[str]:
    nodes = tuple(ast.walk(tree))
    aliases = {
        imported.asname or imported.name
        for node in nodes if isinstance(node, ast.ImportFrom) and node.module in {"builtins", "typing", "typing_extensions"}
        for imported in node.names if imported.name in {"Any", "object"}
    }
    while True:
        before = len(aliases)
        for node in nodes:
            supported = isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)) or type(node).__name__ == "TypeAlias"
            value = getattr(node, "value", None)
            if not supported or not isinstance(value, ast.expr) or not _unsafe_boundary_annotation(value, frozenset(aliases)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else (getattr(node, "target", getattr(node, "name", None)),)
            aliases.update(item.id for target in targets if isinstance(target, ast.AST) for item in ast.walk(target) if isinstance(item, ast.Name))
        if len(aliases) == before:
            return frozenset(aliases)


def _parsed_annotation(annotation: ast.expr) -> ast.expr:
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        try:
            return ast.parse(annotation.value, mode="eval").body
        except SyntaxError:
            return ast.Name(id="Any", ctx=ast.Load())
    return annotation


def _approved_dynamic_imports(path: str) -> frozenset[tuple[str, str]]:
    return APPROVED_DYNAMIC_IMPORTS.get(path, frozenset()) | APPROVED_INTROSPECTION_IMPORTS.get(path, frozenset())


def _imports_store_namespace(record: ImportRecord) -> bool:
    if record.direct_module_import:
        return record.module in CONCRETE_STORE_NAMESPACE_MODULES
    return any(
        (f"{record.module}.{symbol}" if record.module else symbol) in CONCRETE_STORE_NAMESPACE_MODULES
        for symbol in record.symbols
    )


def _runtime_metadata_mutation(node: ast.Call) -> bool:
    name = _expression_name(node.func)
    if name not in {"setattr", "__setattr__", "__setitem__", "setdefault", "update"}:
        return False
    if any(keyword.arg in RUNTIME_METADATA_NAMES for keyword in node.keywords if keyword.arg is not None):
        return True
    key_nodes = list(node.args[1:] if name in {"setattr", "__setattr__", "__setitem__"} else node.args)
    key_nodes.extend(keyword.value for keyword in node.keywords)
    return any(_contains_runtime_metadata_key(value) for value in key_nodes)


def _contains_runtime_metadata_key(node: ast.AST) -> bool:
    return any(
        isinstance(item, ast.Constant) and item.value in RUNTIME_METADATA_NAMES
        or isinstance(item, ast.keyword) and item.arg in RUNTIME_METADATA_NAMES
        for item in ast.walk(node)
    )
