from __future__ import annotations

import argparse
import ast
import copy
import textwrap
from pathlib import Path


GROUPS = (
    ("detail", 5, 10),
    ("downloads", 10, 21),
    ("audit", 21, 22),
    ("reviewer", 22, 23),
    ("final_board", 23, 24),
    ("vault", 24, 25),
    ("attestation", 25, 26),
    ("registry", 26, 27),
    ("portal", 27, 28),
    ("portal_review", 28, 29),
    ("accepted_evidence", 29, 30),
    ("transparency", 30, 31),
    ("acknowledgement", 31, 32),
    ("final_actions", 32, 38),
)


class _HandledReturn(ast.NodeTransformer):
    def visit_Return(self, node: ast.Return) -> ast.Return:
        if node.value is None:
            return ast.copy_location(ast.Return(value=ast.Constant(value=True)), node)
        return node


def split_trust_route(path: Path) -> list[Path]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    route_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TrustRoutes")
    method = next(
        node for node in route_class.body if isinstance(node, ast.FunctionDef) and node.name == "_handle_release_portfolio_audits"
    )
    try_node = method.body[2]
    if not isinstance(try_node, ast.Try) or len(try_node.body) != 39:
        raise ValueError("Unexpected Portfolio Audit route shape")
    directory = path.with_name("trust_portfolio_parts")
    directory.mkdir(exist_ok=True)
    for old in directory.glob("*.py"):
        old.unlink()
    outputs = [_write(directory / "__init__.py", '"""Portfolio Audit HTTP route-family mixins."""\n')]

    rows: list[tuple[str, str]] = []
    root_class = "TrustPortfolioRootRoutes"
    outputs.append(_write(directory / "root.py", _route_module(root_class, _method("_dispatch_portfolio_root", [try_node.body[0]], ("method", "tail")))))
    rows.append(("root", root_class))
    for slug, start, end in GROUPS:
        class_name = "TrustPortfolio" + "".join(part.title() for part in slug.split("_")) + "Routes"
        handler = _method(
            f"_dispatch_portfolio_{slug}",
            try_node.body[start:end],
            ("method", "parts", "portfolio_id", "action"),
        )
        outputs.append(_write(directory / f"{slug}.py", _route_module(class_name, handler)))
        rows.append((slug, class_name))

    import_lines = [
        f"from .trust_portfolio_parts.{slug} import {class_name}" for slug, class_name in rows
    ]
    original_bases = [ast.unparse(base) for base in route_class.bases]
    bases = ", ".join([*original_bases, *(class_name for _slug, class_name in rows)])
    replacement = _main_method(try_node.handlers, [slug for slug, _class_name in rows])
    before = lines[: method.lineno - 1]
    class_line = next(index for index, line in enumerate(before) if line.startswith("class TrustRoutes("))
    before[class_line] = f"class TrustRoutes({bases}):"
    insert_at = class_line
    before[insert_at:insert_at] = [*import_lines, ""]
    updated = [*before, *textwrap.indent(replacement, "    ").splitlines(), *lines[int(method.end_lineno or method.lineno) :]]
    path.write_text("\n".join(updated) + "\n", encoding="utf-8")
    outputs.append(path)
    return outputs


def _method(name: str, statements: list[ast.stmt], arguments: tuple[str, ...]) -> str:
    transformed = [ast.fix_missing_locations(_HandledReturn().visit(copy.deepcopy(row))) for row in statements]
    body = "\n".join(ast.unparse(row) for row in transformed)
    return f"def {name}(self, {', '.join(arguments)}) -> bool:\n{textwrap.indent(body, '    ')}\n    return False"


def _route_module(class_name: str, method: str) -> str:
    return "\n\n".join(
        [
            "from __future__ import annotations",
            "from song_agent.application.interface_persistence import persist_interface_job, write_interface_document",
            "from song_agent.interfaces.api.runtime import *",
            f"class {class_name}:\n{textwrap.indent(method, '    ')}",
        ]
    ) + "\n"


def _main_method(handlers: list[ast.ExceptHandler], slugs: list[str]) -> str:
    body = ast.parse(
        """
prefix = "/api/release-portfolio-audits"
tail = path[len(prefix):]
if self._dispatch_portfolio_root(method, tail):
    return
parts = [part for part in tail.strip("/").split("/") if part]
if not parts:
    self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Audit route not found.")
    return
portfolio_id = parts[0]
action = parts[1] if len(parts) > 1 else ""
"""
    ).body
    for slug in slugs:
        if slug == "root":
            continue
        body.extend(ast.parse(f"if self._dispatch_portfolio_{slug}(method, parts, portfolio_id, action):\n    return").body)
    body.extend(ast.parse('self._send_error(HTTPStatus.NOT_FOUND, "Release Portfolio Audit route not found.")').body)
    node = ast.Try(body=body, handlers=copy.deepcopy(handlers), orelse=[], finalbody=[])
    function = ast.FunctionDef(
        name="_handle_release_portfolio_audits",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self"), ast.arg(arg="method", annotation=ast.Name(id="str")), ast.arg(arg="path", annotation=ast.Name(id="str"))],
            kwonlyargs=[], kw_defaults=[], defaults=[],
        ),
        body=[node], decorator_list=[], returns=ast.Constant(value=None),
    )
    return ast.unparse(ast.fix_missing_locations(function))


def _write(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Split Portfolio Audit HTTP dispatch into route-family mixins.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    path = args.root.resolve() / "song_agent" / "interfaces" / "api" / "routes" / "trust.py"
    outputs = split_trust_route(path)
    oversized = [item for item in outputs if len(item.read_text(encoding="utf-8").splitlines()) > 600]
    if oversized:
        raise RuntimeError(f"Generated oversized Trust route modules: {oversized}")
    print(f"trust portfolio: {len(outputs)} bounded modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
