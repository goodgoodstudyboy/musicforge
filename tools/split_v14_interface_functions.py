from __future__ import annotations

import argparse
import ast
import copy
import textwrap
from collections import defaultdict
from pathlib import Path
from typing import Any

from song_agent.release_check.v14_architecture import evaluate_v14_architecture


class _ReturnAsResult(ast.NodeTransformer):
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        return node

    def visit_Lambda(self, node: ast.Lambda) -> ast.Lambda:
        return node

    def visit_Return(self, node: ast.Return) -> ast.Return:
        value = self.visit(node.value) if node.value is not None else ast.Constant(value=None)
        return ast.copy_location(
            ast.Return(value=ast.Tuple(elts=[ast.Constant(value=True), value], ctx=ast.Load())),
            node,
        )


class _StateNames(ast.NodeTransformer):
    def __init__(self, names: set[str]) -> None:
        self.names = names

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        return node

    def visit_Lambda(self, node: ast.Lambda) -> ast.Lambda:
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id not in self.names:
            return node
        return ast.copy_location(
            ast.Subscript(
                value=ast.Name(id="_split_state", ctx=ast.Load()),
                slice=ast.Constant(value=node.id),
                ctx=node.ctx,
            ),
            node,
        )


class _UnwrapGeneratedReturn(ast.NodeTransformer):
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        return node

    def visit_Return(self, node: ast.Return) -> ast.Return:
        value = node.value
        if (
            isinstance(value, ast.Tuple)
            and len(value.elts) == 2
            and isinstance(value.elts[0], ast.Constant)
            and value.elts[0].value is True
            and isinstance(value.elts[1], ast.Tuple)
            and len(value.elts[1].elts) == 2
        ):
            return ast.copy_location(ast.Return(value=self.visit(value.elts[1])), node)
        return node


def split_interfaces(root: Path, *, write: bool) -> dict[str, Any]:
    rows = evaluate_v14_architecture(root)["metrics"]["interface_oversized_functions"]
    by_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_path[str(row["path"])].append(row)
    changed: list[str] = []
    skipped: list[dict[str, Any]] = []
    for relative, path_rows in sorted(by_path.items()):
        path = root / relative
        source = path.read_text(encoding="utf-8")
        for row in sorted(path_rows, key=lambda item: int(item["line"]), reverse=True):
            try:
                source = _split_one(source, str(row["name"]), int(row["line"]), limit=int(row["limit"]))
            except ValueError as exc:
                skipped.append({"path": relative, "name": row["name"], "reason": str(exc)})
        ast.parse(source, filename=str(path))
        if source != path.read_text(encoding="utf-8"):
            changed.append(relative)
            if write:
                path.write_text(source, encoding="utf-8")
    return {"selected": len(rows), "changed_files": changed, "skipped": skipped}


def _split_one(source: str, name: str, line: int, *, limit: int) -> str:
    tree = ast.parse(source)
    node, parent = _find_function(tree, name, line)
    if isinstance(node, ast.AsyncFunctionDef):
        raise ValueError("async functions require an explicit split")
    if node.args.vararg or node.args.kwarg:
        raise ValueError("variadic functions require an explicit split")
    if "_split_state" in _argument_names(node.args):
        raise ValueError("generated helper requires an explicit semantic split")
    container = _split_container(node, limit)
    statements = container.body if container is not None else node.body
    if len(statements) < 2:
        raise ValueError("single oversized statement requires use-case extraction")
    chunks = _pack(statements, target=70 if limit <= 100 else 90)
    if len(chunks) < 2:
        raise ValueError("function cannot be split into bounded chunks")

    segments: list[list[ast.stmt]] = [chunk for chunk in chunks]
    outside = [child for child in node.body if child is not container] if container else []
    if outside:
        segments.append(outside)
    local_names = _local_names(node) - _argument_names(node.args)
    usage: dict[str, set[int]] = defaultdict(set)
    for index, segment in enumerate(segments):
        for local in _used_names(segment) & local_names:
            usage[local].add(index)
    state_names = {local for local, indexes in usage.items() if len(indexes) > 1}

    helpers = [
        _helper_function(node, parent, name, index, chunk, state_names)
        for index, chunk in enumerate(chunks, start=1)
    ]
    wrapper = copy.deepcopy(node)
    calls = _helper_calls(node, parent, name, len(chunks))
    if container is None:
        wrapper.body = calls
    else:
        target = _matching_container(wrapper, container)
        target.body = calls
        wrapper.body.insert(0, _state_assignment())
        transformer = _StateNames(state_names)
        wrapper.body[1:] = [transformer.visit(item) for item in wrapper.body[1:]]
    if container is None:
        wrapper.body.insert(0, _state_assignment())
    ast.fix_missing_locations(wrapper)
    generated = [*helpers, wrapper]
    generated_source = "\n\n".join(ast.unparse(item) for item in generated)
    indent = "    " if isinstance(parent, ast.ClassDef) else ""
    if indent:
        generated_source = textwrap.indent(generated_source, indent)
    start = _source_start(node) - 1
    end = int(node.end_lineno or node.lineno)
    lines = source.splitlines()
    replacement = generated_source.splitlines()
    return "\n".join([*lines[:start], *replacement, *lines[end:]]) + "\n"


def _helper_function(
    original: ast.FunctionDef,
    parent: ast.AST,
    original_name: str,
    index: int,
    chunk: list[ast.stmt],
    state_names: set[str],
) -> ast.FunctionDef:
    body = copy.deepcopy(chunk)
    body = [_StateNames(state_names).visit(item) for item in body]
    transformer = _ReturnAsResult()
    body = [transformer.visit(item) for item in body]
    body.append(
        ast.Return(
            value=ast.Tuple(elts=[ast.Constant(value=False), ast.Constant(value=None)], ctx=ast.Load())
        )
    )
    original_args = [*original.args.posonlyargs, *original.args.args, *original.args.kwonlyargs]
    args = ast.arguments(
        posonlyargs=[],
        args=[*(copy.deepcopy(item) for item in original_args), ast.arg(arg="_split_state")],
        vararg=None,
        kwonlyargs=[],
        kw_defaults=[],
        kwarg=None,
        defaults=[],
    )
    helper = ast.FunctionDef(
        name=_helper_name(original_name, index),
        args=args,
        body=body,
        decorator_list=[],
        returns=None,
        type_comment=None,
    )
    return ast.fix_missing_locations(helper)


def _helper_calls(original: ast.FunctionDef, parent: ast.AST, name: str, count: int) -> list[ast.stmt]:
    argument_names = [arg.arg for arg in [*original.args.posonlyargs, *original.args.args, *original.args.kwonlyargs]]
    is_method = isinstance(parent, ast.ClassDef)
    if is_method and argument_names and argument_names[0] in {"self", "cls"}:
        call_arguments = argument_names[1:]
    else:
        call_arguments = argument_names
    rows: list[ast.stmt] = []
    for index in range(1, count + 1):
        function: ast.expr
        if is_method:
            function = ast.Attribute(
                value=ast.Name(id=argument_names[0], ctx=ast.Load()),
                attr=_helper_name(name, index),
                ctx=ast.Load(),
            )
        else:
            function = ast.Name(id=_helper_name(name, index), ctx=ast.Load())
        call = ast.Call(
            func=function,
            args=[*(ast.Name(id=item, ctx=ast.Load()) for item in call_arguments), ast.Name(id="_split_state", ctx=ast.Load())],
            keywords=[],
        )
        rows.extend(
            [
                ast.Assign(targets=[ast.Name(id="_split_result", ctx=ast.Store())], value=call),
                ast.If(
                    test=ast.Subscript(value=ast.Name(id="_split_result", ctx=ast.Load()), slice=ast.Constant(value=0), ctx=ast.Load()),
                    body=[ast.Return(value=ast.Subscript(value=ast.Name(id="_split_result", ctx=ast.Load()), slice=ast.Constant(value=1), ctx=ast.Load()))],
                    orelse=[],
                ),
            ]
        )
    return [ast.fix_missing_locations(item) for item in rows]


def _helper_name(original_name: str, index: int) -> str:
    prefix = "" if original_name.startswith("_") else "_"
    return f"{prefix}{original_name}_part_{index:02d}"


def _state_assignment() -> ast.Assign:
    return ast.Assign(
        targets=[ast.Name(id="_split_state", ctx=ast.Store())],
        value=ast.Dict(keys=[], values=[]),
    )


def _split_container(node: ast.FunctionDef, limit: int) -> ast.Try | ast.With | None:
    candidates = [
        child
        for child in node.body
        if isinstance(child, (ast.Try, ast.With))
        and len(child.body) >= 2
        and int(child.end_lineno or child.lineno) - int(child.lineno) + 1 >= limit
    ]
    return max(candidates, key=lambda item: int(item.end_lineno or item.lineno) - int(item.lineno)) if candidates else None


def _matching_container(wrapper: ast.FunctionDef, original: ast.Try | ast.With) -> ast.Try | ast.With:
    matches = [
        child
        for child in wrapper.body
        if isinstance(child, type(original)) and child.lineno == original.lineno
    ]
    if len(matches) != 1:
        raise ValueError("split container could not be reconstructed")
    return matches[0]


def _pack(statements: list[ast.stmt], *, target: int) -> list[list[ast.stmt]]:
    groups: list[list[ast.stmt]] = []
    current: list[ast.stmt] = []
    size = 0
    for statement in statements:
        lines = int(statement.end_lineno or statement.lineno) - int(statement.lineno) + 1
        if current and size + lines > target:
            groups.append(current)
            current = []
            size = 0
        current.append(statement)
        size += lines
    if current:
        groups.append(current)
    return groups


def _find_function(tree: ast.Module, name: str, line: int) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef, ast.AST]:
    for parent in [tree, *(node for node in ast.walk(tree) if isinstance(node, ast.ClassDef))]:
        for child in getattr(parent, "body", []):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == name and child.lineno == line:
                return child, parent
    raise ValueError(f"function not found: {name}:{line}")


def _local_names(node: ast.FunctionDef) -> set[str]:
    names = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del))
    }
    for child in ast.walk(node):
        if isinstance(child, (ast.Import, ast.ImportFrom)):
            names.update(alias.asname or alias.name.split(".", 1)[0] for alias in child.names)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child is not node:
            names.add(child.name)
    return names


def _argument_names(args: ast.arguments) -> set[str]:
    return {
        item.arg
        for item in [*args.posonlyargs, *args.args, *args.kwonlyargs]
    } | ({args.vararg.arg} if args.vararg else set()) | ({args.kwarg.arg} if args.kwarg else set())


def _used_names(nodes: list[ast.stmt]) -> set[str]:
    return {child.id for node in nodes for child in ast.walk(node) if isinstance(child, ast.Name)}


def _source_start(node: ast.AST) -> int:
    decorators = getattr(node, "decorator_list", ())
    return min([int(node.lineno), *(int(item.lineno) for item in decorators)])


def repair_recursive_split(root: Path) -> int:
    repairs = (
        (
            root / "song_agent/interfaces/api/routes/quality_parts/audio_fix_sprint.py",
            "_handle_audio_campaign_route_part_02",
        ),
        (
            root / "song_agent/interfaces/api/routes/trust_portfolio_parts/acknowledgement.py",
            "_dispatch_portfolio_acknowledgement_part_01",
        ),
    )
    count = 0
    for path, parent_name in repairs:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        owner = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        functions = {
            node.name: node for node in owner.body if isinstance(node, ast.FunctionDef)
        }
        parent = functions.get(parent_name)
        first = functions.get(parent_name + "_part_01")
        second = functions.get(parent_name + "_part_02")
        if parent is None or first is None or second is None:
            continue
        body: list[ast.stmt] = []
        unwrap = _UnwrapGeneratedReturn()
        for helper in (first, second):
            helper_body = copy.deepcopy(helper.body)
            if helper_body and _is_generated_default_return(helper_body[-1]):
                helper_body.pop()
            body.extend(unwrap.visit(item) for item in helper_body)
        rebuilt = copy.deepcopy(parent)
        rebuilt.body = body
        rebuilt = ast.fix_missing_locations(rebuilt)
        replacement = textwrap.indent(ast.unparse(rebuilt), "    ").splitlines()
        lines = source.splitlines()
        start = int(first.lineno) - 1
        end = int(parent.end_lineno or parent.lineno)
        path.write_text("\n".join([*lines[:start], *replacement, *lines[end:]]) + "\n", encoding="utf-8")
        count += 1
    return count


def split_residual_route_helpers(root: Path) -> int:
    specs = (
        (
            root / "song_agent/interfaces/api/routes/quality_parts/audio_fix_sprint.py",
            "_handle_audio_campaign_route_part_02",
            "action",
            ("parts", "campaign_id", "action"),
        ),
        (
            root / "song_agent/interfaces/api/routes/trust_portfolio_parts/acknowledgement.py",
            "_dispatch_portfolio_acknowledgement_part_01",
            "subaction",
            ("query_profile", "subaction"),
        ),
    )
    changed = 0
    for path, function_name, anchor, extras in specs:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        owner = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        function = next(
            (node for node in owner.body if isinstance(node, ast.FunctionDef) and node.name == function_name),
            None,
        )
        if function is None:
            continue
        if not function.body or not isinstance(function.body[0], ast.If):
            raise ValueError(f"Unexpected generated route helper shape: {path}:{function_name}")
        outer = function.body[0]
        anchor_index = next(
            index
            for index, statement in enumerate(outer.body)
            if anchor in _assigned_names(statement)
        )
        prefix = copy.deepcopy(outer.body[: anchor_index + 1])
        remainder = outer.body[anchor_index + 1 :]
        groups = _pack(remainder, target=55)
        if len(groups) < 2:
            raise ValueError(f"Residual route helper did not split: {path}:{function_name}")
        helpers: list[ast.FunctionDef] = []
        original_names = [arg.arg for arg in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]]
        helper_names = [*original_names, *(name for name in extras if name not in original_names)]
        for index, group in enumerate(groups, start=1):
            helper = ast.FunctionDef(
                name=f"{function_name}_actions_{index:02d}",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[ast.arg(arg=name) for name in helper_names],
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults=[],
                ),
                body=[*copy.deepcopy(group), ast.Return(value=ast.Tuple(elts=[ast.Constant(value=False), ast.Constant(value=None)], ctx=ast.Load()))],
                decorator_list=[],
            )
            helpers.append(ast.fix_missing_locations(helper))
        calls: list[ast.stmt] = []
        for index in range(1, len(groups) + 1):
            call = ast.Call(
                func=ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()), attr=f"{function_name}_actions_{index:02d}", ctx=ast.Load()),
                args=[ast.Name(id=name, ctx=ast.Load()) for name in helper_names[1:]],
                keywords=[],
            )
            calls.extend(
                [
                    ast.Assign(targets=[ast.Name(id="_split_action_result", ctx=ast.Store())], value=call),
                    ast.If(
                        test=ast.Subscript(value=ast.Name(id="_split_action_result", ctx=ast.Load()), slice=ast.Constant(value=0), ctx=ast.Load()),
                        body=[ast.Return(value=ast.Name(id="_split_action_result", ctx=ast.Load()))],
                        orelse=[],
                    ),
                ]
            )
        rebuilt = copy.deepcopy(function)
        rebuilt_outer = rebuilt.body[0]
        assert isinstance(rebuilt_outer, ast.If)
        rebuilt_outer.body = [*prefix, *(ast.fix_missing_locations(item) for item in calls)]
        generated = [*helpers, ast.fix_missing_locations(rebuilt)]
        replacement = textwrap.indent("\n\n".join(ast.unparse(item) for item in generated), "    ").splitlines()
        lines = source.splitlines()
        start = int(function.lineno) - 1
        end = int(function.end_lineno or function.lineno)
        path.write_text("\n".join([*lines[:start], *replacement, *lines[end:]]) + "\n", encoding="utf-8")
        changed += 1
    return changed


def _assigned_names(node: ast.AST) -> set[str]:
    return {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store)
    }


def _is_generated_default_return(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Return)
        and isinstance(node.value, ast.Tuple)
        and len(node.value.elts) == 2
        and isinstance(node.value.elts[0], ast.Constant)
        and node.value.elts[0].value is False
        and isinstance(node.value.elts[1], ast.Constant)
        and node.value.elts[1].value is None
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Split oversized v14 interface functions at route boundaries.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--repair-recursive", action="store_true")
    parser.add_argument("--split-residual-routes", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    if args.repair_recursive:
        print({"repaired": repair_recursive_split(root)})
        return 0
    if args.split_residual_routes:
        print({"split_residual_routes": split_residual_route_helpers(root)})
        return 0
    result = split_interfaces(root, write=args.write)
    print(result)
    return 0 if not result["skipped"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
