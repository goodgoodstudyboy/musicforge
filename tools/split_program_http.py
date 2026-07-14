from __future__ import annotations

import argparse
import ast
import copy
import subprocess
import textwrap
from pathlib import Path


GROUPS = (
    ("core", 6, 14),
    ("handoff", 14, 29),
    ("vault", 29, 36),
    ("vault_operations", 36, 49),
    ("continuity", 49, 60),
    ("continuity_kit", 60, 69),
    ("acceptance", 69, 78),
    ("acceptance_change", 78, 87),
    ("command_center", 87, 94),
    ("command_center_signoff", 94, 107),
    ("receiver_acceptance", 107, 117),
    ("receiver_acceptance_change", 117, 125),
    ("operations", 125, 135),
    ("download", 135, 136),
)


class _HandledReturn(ast.NodeTransformer):
    def visit_Return(self, node: ast.Return) -> ast.Return:
        if node.value is None:
            return ast.copy_location(ast.Return(value=ast.Constant(value=True)), node)
        return node


def split_program_http(path: Path, *, source: str | None = None) -> list[Path]:
    source = path.read_text(encoding="utf-8") if source is None else source
    tree = ast.parse(source, filename=str(path))
    lines = source.splitlines()
    application = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProgramHttpApplication"
    )
    dispatch = next(
        node for node in application.body if isinstance(node, ast.FunctionDef) and node.name == "dispatch"
    )
    if len(dispatch.body) != 1 or not isinstance(dispatch.body[0], ast.Try):
        raise ValueError("Unexpected Program HTTP dispatch shape")
    try_node = dispatch.body[0]
    if len(try_node.body) < 136:
        raise ValueError("Program HTTP dispatch was already split or changed unexpectedly")

    routes = path.with_name("http_routes")
    routes.mkdir(exist_ok=True)
    for old in routes.glob("*.py"):
        old.unlink()
    outputs = [_write(routes / "__init__.py", '"""Program HTTP route-family mixins."""\n')]

    route_classes: list[tuple[str, str]] = []
    root_class = "ProgramRootHttpRoutes"
    root_method = _handler_method("_dispatch_root", [try_node.body[0]], ("method", "path"))
    outputs.append(_write(routes / "root.py", _route_module(root_class, root_method)))
    route_classes.append(("root", root_class))

    for slug, start, end in GROUPS:
        class_name = "Program" + "".join(part.title() for part in slug.split("_")) + "HttpRoutes"
        method = _handler_method(f"_dispatch_{slug}", try_node.body[start:end], ("method", "program_id", "tail"))
        output = routes / f"{slug}.py"
        outputs.append(_write(output, _route_module(class_name, method)))
        route_classes.append((slug, class_name))

    preserved = [
        node for node in application.body if isinstance(node, ast.FunctionDef) and node.name != "dispatch"
    ]
    import_source = "\n".join(
        _node_source(node, lines)
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
    )
    top_level_source = "\n\n".join(
        _node_source(node, lines)
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.Assign, ast.AnnAssign)) and node is not application
    )
    mixin_imports = "\n".join(
        f"from .http_routes.{slug} import {class_name}" for slug, class_name in route_classes
    )
    bases = ", ".join(class_name for _slug, class_name in route_classes)
    methods = "\n\n".join(_node_source(node, lines) for node in preserved)
    main_dispatch = _main_dispatch(try_node.handlers, [slug for slug, _class_name in route_classes])
    document = "\n\n".join(
        [
            "from __future__ import annotations",
            import_source,
            mixin_imports,
            top_level_source,
            f"class ProgramHttpApplication({bases}):\n"
            + textwrap.indent(textwrap.dedent(methods), "    ")
            + "\n\n"
            + textwrap.indent(main_dispatch, "    "),
        ]
    ) + "\n"
    path.write_text(document, encoding="utf-8")
    outputs.append(path)
    return outputs


def _handler_method(name: str, statements: list[ast.stmt], arguments: tuple[str, ...]) -> str:
    transformed = [
        ast.fix_missing_locations(_HandledReturn().visit(copy.deepcopy(statement))) for statement in statements
    ]
    body = "\n".join(ast.unparse(statement) for statement in transformed)
    args = ", ".join(("self", *arguments))
    return f"def {name}({args}) -> bool:\n{textwrap.indent(body, '    ')}\n    return False"


def _route_module(class_name: str, method: str) -> str:
    return "\n\n".join(
        [
            "from __future__ import annotations",
            "from http import HTTPStatus",
            f"class {class_name}:\n{textwrap.indent(method, '    ')}",
        ]
    ) + "\n"


def _main_dispatch(handlers: list[ast.ExceptHandler], slugs: list[str]) -> str:
    route_calls = [slug for slug in slugs if slug != "root"]
    body: list[ast.stmt] = ast.parse(
        """
if self._dispatch_root(method, path):
    return
prefix = "/api/unified-release-programs/"
if not path.startswith(prefix):
    self._send_error(HTTPStatus.NOT_FOUND, "Unified Release Program route not found.")
    return
parts = path.removeprefix(prefix).strip("/").split("/")
program_id = parts[0]
tail = "/" + "/".join(parts[1:]) if len(parts) > 1 else ""
"""
    ).body
    for slug in route_calls:
        body.extend(
            ast.parse(
                f"if self._dispatch_{slug}(method, program_id, tail):\n    return"
            ).body
        )
    body.extend(
        ast.parse(
            'self._send_error(HTTPStatus.NOT_FOUND, "Unified Release Program route not found.")'
        ).body
    )
    node = ast.Try(body=body, handlers=copy.deepcopy(handlers), orelse=[], finalbody=[])
    function = ast.FunctionDef(
        name="dispatch",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self"), ast.arg(arg="method", annotation=ast.Name(id="str")), ast.arg(arg="path", annotation=ast.Name(id="str"))],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[node],
        decorator_list=[],
        returns=ast.Constant(value=None),
    )
    return ast.unparse(ast.fix_missing_locations(function))


def _node_source(node: ast.AST, lines: list[str]) -> str:
    decorators = getattr(node, "decorator_list", ())
    start = min([node.lineno, *(item.lineno for item in decorators)])
    return "\n".join(lines[start - 1 : int(node.end_lineno or node.lineno)])


def _write(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Split Program HTTP dispatch into route-family adapters.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--git-ref")
    args = parser.parse_args()
    root = args.root.resolve()
    path = root / "song_agent" / "application" / "program" / "http.py"
    source = None
    if args.git_ref:
        source = subprocess.run(
            ["git", "show", f"{args.git_ref}:{path.relative_to(root).as_posix()}"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout
    outputs = split_program_http(path, source=source)
    oversized = [item for item in outputs if len(item.read_text(encoding="utf-8").splitlines()) > 600]
    if oversized:
        raise RuntimeError(f"Generated oversized Program HTTP modules: {oversized}")
    print(f"program http: {len(outputs)} bounded modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
