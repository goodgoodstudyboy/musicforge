from __future__ import annotations

import argparse
import ast
import copy
import textwrap
from pathlib import Path


STUDIO_GROUPS = (
    ("system", 7, 33),
    ("jobs", 33, 37),
    ("resources", 37, 46),
    ("acceptance_routes", 46, 64),
    ("acceptance_items", 64, 85),
    ("distribution", 85, 93),
    ("library", 93, 109),
    ("dynamic", 109, 131),
)
PROGRAM_GROUPS = (
    ("reviews", 6, 8),
    ("drifts", 8, 10),
    ("evidence_root", 10, 11),
    ("evidence_detail", 11, 12),
    ("boards", 12, 14),
    ("core", 14, 24),
    ("handoff", 24, 34),
)


class _HandledReturn(ast.NodeTransformer):
    def visit_Return(self, node: ast.Return) -> ast.Return:
        if node.value is None:
            return ast.copy_location(ast.Return(value=ast.Constant(value=True)), node)
        return node


def split_studio(path: Path) -> tuple[list[Path], tuple[str, ...]]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    route_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "StudioRoutes")
    method = next(node for node in route_class.body if isinstance(node, ast.FunctionDef) and node.name == "_handle_request")
    try_node = method.body[0]
    if not isinstance(try_node, ast.Try) or len(try_node.body) != 132:
        raise ValueError("Unexpected Studio dispatch shape")
    directory = path.with_name("studio_dispatch_parts")
    directory.mkdir(exist_ok=True)
    for old in directory.glob("*.py"):
        old.unlink()
    outputs = [_write(directory / "__init__.py", '"""Manifest-driven Studio route-family mixins."""\n')]
    mixins: list[tuple[str, str, str]] = []
    for slug, start, end in STUDIO_GROUPS:
        class_name = "Studio" + slug.title() + "Dispatch"
        method_name = f"_dispatch_studio_{slug}"
        handler = _handler(method_name, try_node.body[start:end], ("method", "path", "parsed"))
        source_text = "\n\n".join(
            [
                "from __future__ import annotations",
                "from song_agent.application.interface_persistence import persist_interface_job, write_interface_document",
                "from song_agent.interfaces.api.runtime import *",
                "from song_agent.interfaces.api.routes.program_registry import PROGRAM_ROUTE_REGISTRY",
                f"class {class_name}:\n{textwrap.indent(handler, '    ')}",
            ]
        ) + "\n"
        outputs.append(_write(directory / f"{slug}.py", source_text))
        mixins.append((slug, class_name, method_name))

    replacement = _studio_main(try_node.handlers)
    _replace_method_and_bases(path, lines, route_class, method, mixins, replacement, "studio_dispatch_parts")
    outputs.append(path)
    return outputs, tuple(row[2] for row in mixins)


def split_program(path: Path) -> list[Path]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    route_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProgramRoutes")
    method = next(
        node for node in route_class.body if isinstance(node, ast.FunctionDef) and node.name == "_handle_unified_command_centers_route"
    )
    try_node = method.body[0]
    if not isinstance(try_node, ast.Try) or len(try_node.body) != 35:
        raise ValueError("Unexpected Unified Command Center route shape")
    directory = path.with_name("program_ucc_parts")
    directory.mkdir(exist_ok=True)
    for old in directory.glob("*.py"):
        old.unlink()
    outputs = [_write(directory / "__init__.py", '"""Unified Command Center route-family mixins."""\n')]
    mixins: list[tuple[str, str, str]] = []
    root_class = "ProgramUccRootRoutes"
    root_method = "_dispatch_ucc_root"
    outputs.append(
        _write(
            directory / "root.py",
            _runtime_route_module(root_class, _handler(root_method, [try_node.body[0]], ("method", "path"))),
        )
    )
    mixins.append(("root", root_class, root_method))
    for slug, start, end in PROGRAM_GROUPS:
        class_name = "ProgramUcc" + slug.title() + "Routes"
        method_name = f"_dispatch_ucc_{slug}"
        handler = _handler(method_name, try_node.body[start:end], ("method", "center_id", "tail"))
        outputs.append(_write(directory / f"{slug}.py", _runtime_route_module(class_name, handler)))
        mixins.append((slug, class_name, method_name))
    replacement = _program_main(try_node.handlers, [slug for slug, _class, _method in mixins])
    _replace_method_and_bases(path, lines, route_class, method, mixins, replacement, "program_ucc_parts")
    outputs.append(path)
    return outputs


def _handler(name: str, statements: list[ast.stmt], arguments: tuple[str, ...]) -> str:
    transformed = [ast.fix_missing_locations(_HandledReturn().visit(copy.deepcopy(row))) for row in statements]
    body = "\n".join(ast.unparse(row) for row in transformed)
    return f"def {name}(self, {', '.join(arguments)}) -> bool:\n{textwrap.indent(body, '    ')}\n    return False"


def _studio_main(handlers: list[ast.ExceptHandler]) -> str:
    body = ast.parse(
        """
parsed = urlparse(self.path)
path = parsed.path
if method == "GET" and path.startswith("/assets/musicforge/"):
    try:
        self._send_javascript(web_script(path.removeprefix("/assets/musicforge/")))
    except FileNotFoundError:
        self._send_error(HTTPStatus.NOT_FOUND, "Studio script module not found.")
    return
if self._auth_required(path) and not self._is_authorized():
    self._send_unauthorized()
    return
if method == "GET" and path == "/":
    self._send_html(panel_html())
    return
if method == "GET" and path == "/api/info":
    self._send_json(api_info(self.auth_config, authorized=(not self.auth_config.enabled) or self._is_authorized()))
    return
if method == "GET" and path == "/api/template":
    self._send_json(api_template())
    return
if self.route_registry.dispatch(self, method, path, parsed):
    return
self._send_error(HTTPStatus.NOT_FOUND, "Route not found.")
"""
    ).body
    node = ast.Try(body=body, handlers=copy.deepcopy(handlers), orelse=[], finalbody=[])
    function = ast.FunctionDef(
        name="_handle_request",
        args=ast.arguments(posonlyargs=[], args=[ast.arg(arg="self"), ast.arg(arg="method", annotation=ast.Name(id="str"))], kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=[node], decorator_list=[], returns=ast.Constant(value=None),
    )
    return ast.unparse(ast.fix_missing_locations(function))


def _program_main(handlers: list[ast.ExceptHandler], slugs: list[str]) -> str:
    body = ast.parse(
        """
if self._dispatch_ucc_root(method, path):
    return
prefix = "/api/unified-command-centers/"
if not path.startswith(prefix):
    self._send_error(HTTPStatus.NOT_FOUND, "Unified Command Center route not found.")
    return
parts = path.removeprefix(prefix).strip("/").split("/")
center_id = parts[0]
tail = "/" + "/".join(parts[1:]) if len(parts) > 1 else ""
"""
    ).body
    for slug in slugs:
        if slug == "root":
            continue
        body.extend(ast.parse(f"if self._dispatch_ucc_{slug}(method, center_id, tail):\n    return").body)
    body.extend(ast.parse('self._send_error(HTTPStatus.NOT_FOUND, "Unified Command Center route not found.")').body)
    node = ast.Try(body=body, handlers=copy.deepcopy(handlers), orelse=[], finalbody=[])
    function = ast.FunctionDef(
        name="_handle_unified_command_centers_route",
        args=ast.arguments(posonlyargs=[], args=[ast.arg(arg="self"), ast.arg(arg="method", annotation=ast.Name(id="str")), ast.arg(arg="path", annotation=ast.Name(id="str"))], kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=[node], decorator_list=[], returns=ast.Constant(value=None),
    )
    return ast.unparse(ast.fix_missing_locations(function))


def _runtime_route_module(class_name: str, method: str) -> str:
    return "\n\n".join(
        [
            "from __future__ import annotations",
            "from song_agent.application.interface_persistence import persist_interface_job, write_interface_document",
            "from song_agent.interfaces.api.runtime import *",
            f"class {class_name}:\n{textwrap.indent(method, '    ')}",
        ]
    ) + "\n"


def _replace_method_and_bases(
    path: Path,
    lines: list[str],
    route_class: ast.ClassDef,
    method: ast.FunctionDef,
    mixins: list[tuple[str, str, str]],
    replacement: str,
    package: str,
) -> None:
    before = lines[: method.lineno - 1]
    class_line = next(index for index, line in enumerate(before) if line.startswith(f"class {route_class.name}("))
    original_bases = [ast.unparse(base) for base in route_class.bases]
    before[class_line] = f"class {route_class.name}({', '.join([*original_bases, *(row[1] for row in mixins)])}):"
    imports = [f"from .{package}.{slug} import {class_name}" for slug, class_name, _method in mixins]
    before[class_line:class_line] = [*imports, ""]
    updated = [*before, *textwrap.indent(replacement, "    ").splitlines(), *lines[int(method.end_lineno or method.lineno) :]]
    path.write_text("\n".join(updated) + "\n", encoding="utf-8")


def _write(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Split the active API dispatchers into manifest route families.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    routes = args.root.resolve() / "song_agent" / "interfaces" / "api" / "routes"
    studio_outputs, handlers = split_studio(routes / "studio.py")
    program_outputs = split_program(routes / "program.py")
    oversized = [
        path
        for path in [*studio_outputs, *program_outputs]
        if len(path.read_text(encoding="utf-8").splitlines()) > 400
    ]
    if oversized:
        raise RuntimeError(f"Generated oversized active dispatch modules: {oversized}")
    print("studio dispatch handlers: " + ",".join(handlers))
    print(f"active dispatch: {len(studio_outputs) + len(program_outputs)} bounded modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
