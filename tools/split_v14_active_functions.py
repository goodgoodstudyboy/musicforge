from __future__ import annotations

import argparse
import ast
import copy
import re
from pathlib import Path

try:
    from tools.split_v14_interface_functions import _split_one
except ModuleNotFoundError:  # Direct script execution puts tools/ on sys.path.
    from split_v14_interface_functions import _split_one


SPECS = (
    ("song_agent/domains/trust/ga_readiness.py", "build_ga_readiness_report", 200),
    ("song_agent/application/legacy/release_signoff.py", "execute", 150),
    ("song_agent/domains/trust/ga_readiness_verifier.py", "verify_ga_readiness_report", 200),
    ("song_agent/domains/studio/song_editor.py", "apply_editor_patch", 200),
)


def split_active_functions(root: Path, *, write: bool) -> dict[str, object]:
    changed: list[str] = []
    skipped: list[dict[str, str]] = []
    for relative, function_name, limit in SPECS:
        path = root / relative
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
            and "_split_state" not in {arg.arg for arg in node.args.args}
        ]
        if not functions:
            continue
        node = functions[0]
        lines = int(node.end_lineno or node.lineno) - int(node.lineno) + 1
        if lines <= limit:
            continue
        if any(isinstance(child, (ast.Import, ast.ImportFrom)) for child in ast.walk(node)):
            skipped.append({"path": relative, "function": function_name, "reason": "local import"})
            continue
        try:
            migrated = _split_one(source, function_name, node.lineno, limit=limit)
        except ValueError as exc:
            skipped.append({"path": relative, "function": function_name, "reason": str(exc)})
            continue
        ast.parse(migrated, filename=str(path))
        changed.append(relative)
        if write:
            path.write_text(migrated, encoding="utf-8")
    if _split_editor_operation_dispatch(root, write=write):
        changed.append("song_agent/domains/studio/song_editor.py")
    if _split_audio_campaign_parser(root, write=write):
        changed.append("song_agent/interfaces/cli/commands/quality_parts/audio_fix_sprint.py")
    changed.extend(_privatize_generated_helpers(root, write=write))
    return {"changed_files": sorted(set(changed)), "skipped": skipped}


def _privatize_generated_helpers(root: Path, *, write: bool) -> list[str]:
    changed: list[str] = []
    pattern = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z][A-Za-z0-9_]*_part_\d{2})(?![A-Za-z0-9_])")
    for relative_root in (
        "song_agent/platform",
        "song_agent/application",
        "song_agent/domains",
        "song_agent/capabilities",
        "song_agent/interfaces",
    ):
        for path in sorted((root / relative_root).rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            generated = {
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and pattern.fullmatch(node.name)
                and "_split_state" in {arg.arg for arg in node.args.args}
            }
            if not generated:
                continue
            migrated = source
            for name in sorted(generated, key=len, reverse=True):
                migrated = re.sub(
                    rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])",
                    f"_{name}",
                    migrated,
                )
            ast.parse(migrated, filename=str(path))
            changed.append(path.relative_to(root).as_posix())
            if write:
                path.write_text(migrated, encoding="utf-8")
    return changed


def _split_audio_campaign_parser(root: Path, *, write: bool) -> bool:
    path = root / "song_agent/interfaces/cli/commands/quality_parts/audio_fix_sprint.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    function = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_build_audio_campaign_parser_part_01"
        ),
        None,
    )
    if function is None:
        return False
    lines = int(function.end_lineno or function.lineno) - int(function.lineno) + 1
    if lines <= 80:
        return False
    if len(function.body) < 54:
        raise ValueError("Audio Campaign parser helper has an unexpected shape")
    cut = 52
    first_body = copy.deepcopy(function.body[:cut])
    second_body = copy.deepcopy(function.body[cut:-1])
    helpers = [
        ast.FunctionDef(
            name="_build_audio_campaign_parser_core",
            args=copy.deepcopy(function.args),
            body=[*first_body, ast.Return(value=ast.Constant(value=None))],
            decorator_list=[],
        ),
        ast.FunctionDef(
            name="_build_audio_campaign_parser_governance",
            args=copy.deepcopy(function.args),
            body=[*second_body, ast.Return(value=ast.Constant(value=None))],
            decorator_list=[],
        ),
    ]
    wrapper = copy.deepcopy(function)
    wrapper.body = [
        ast.Expr(
            value=ast.Call(
                func=ast.Name(id="_build_audio_campaign_parser_core", ctx=ast.Load()),
                args=[ast.Name(id="_split_state", ctx=ast.Load())],
                keywords=[],
            )
        ),
        ast.Expr(
            value=ast.Call(
                func=ast.Name(id="_build_audio_campaign_parser_governance", ctx=ast.Load()),
                args=[ast.Name(id="_split_state", ctx=ast.Load())],
                keywords=[],
            )
        ),
        ast.Return(
            value=ast.Tuple(
                elts=[ast.Constant(value=False), ast.Constant(value=None)],
                ctx=ast.Load(),
            )
        ),
    ]
    generated = [*(ast.fix_missing_locations(node) for node in helpers), ast.fix_missing_locations(wrapper)]
    replacement = "\n\n".join(ast.unparse(node) for node in generated)
    source_lines = source.splitlines()
    migrated = "\n".join(
        [
            *source_lines[: int(function.lineno) - 1],
            *replacement.splitlines(),
            *source_lines[int(function.end_lineno or function.lineno) :],
        ]
    ) + "\n"
    ast.parse(migrated, filename=str(path))
    if write:
        path.write_text(migrated, encoding="utf-8")
    return True


def _split_editor_operation_dispatch(root: Path, *, write: bool) -> bool:
    path = root / "song_agent/domains/studio/song_editor.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    function = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "apply_editor_patch_part_02"
        ),
        None,
    )
    if function is None:
        return False
    lines = int(function.end_lineno or function.lineno) - int(function.lineno) + 1
    if lines <= 200:
        return False
    loop = next((node for node in function.body if isinstance(node, ast.For)), None)
    if loop is None:
        raise ValueError("Editor operation dispatcher has no operation loop")
    dispatch = next((node for node in loop.body if isinstance(node, ast.If)), None)
    if dispatch is None:
        raise ValueError("Editor operation dispatcher has no operation chain")
    branches = _if_chain(dispatch)
    groups = _pack_if_branches(branches, target_lines=150)
    helpers: list[ast.FunctionDef] = []
    calls: list[ast.stmt] = []
    for index, group in enumerate(groups, start=1):
        helper_name = f"_apply_editor_patch_operations_{index:02d}"
        chain = _build_if_chain(group)
        helpers.append(
            ast.fix_missing_locations(
                ast.FunctionDef(
                    name=helper_name,
                    args=ast.arguments(
                        posonlyargs=[],
                        args=[
                            ast.arg(arg="parent_plan"),
                            ast.arg(arg="operation"),
                            ast.arg(arg="op"),
                            ast.arg(arg="_split_state"),
                        ],
                        vararg=None,
                        kwonlyargs=[],
                        kw_defaults=[],
                        kwarg=None,
                        defaults=[],
                    ),
                    body=[chain],
                    decorator_list=[],
                    returns=ast.Name(id="bool", ctx=ast.Load()),
                )
            )
        )
        call = ast.Call(
            func=ast.Name(id=helper_name, ctx=ast.Load()),
            args=[
                ast.Name(id="parent_plan", ctx=ast.Load()),
                ast.Name(id="operation", ctx=ast.Load()),
                ast.Name(id="op", ctx=ast.Load()),
                ast.Name(id="_split_state", ctx=ast.Load()),
            ],
            keywords=[],
        )
        calls.append(
            ast.fix_missing_locations(
                ast.If(test=call, body=[ast.Continue()], orelse=[])
            )
        )
    dispatch_index = loop.body.index(dispatch)
    rebuilt = copy.deepcopy(function)
    rebuilt_loop = next(node for node in rebuilt.body if isinstance(node, ast.For))
    rebuilt_loop.body = [*rebuilt_loop.body[:dispatch_index], *calls, *rebuilt_loop.body[dispatch_index + 1 :]]
    generated = [*helpers, ast.fix_missing_locations(rebuilt)]
    replacement = "\n\n".join(ast.unparse(node) for node in generated)
    source_lines = source.splitlines()
    migrated = "\n".join(
        [
            *source_lines[: int(function.lineno) - 1],
            *replacement.splitlines(),
            *source_lines[int(function.end_lineno or function.lineno) :],
        ]
    ) + "\n"
    ast.parse(migrated, filename=str(path))
    if write:
        path.write_text(migrated, encoding="utf-8")
    return True


def _if_chain(node: ast.If) -> list[tuple[ast.expr, list[ast.stmt]]]:
    branches: list[tuple[ast.expr, list[ast.stmt]]] = []
    current = node
    while True:
        branches.append((copy.deepcopy(current.test), copy.deepcopy(current.body)))
        if not current.orelse:
            break
        if len(current.orelse) != 1 or not isinstance(current.orelse[0], ast.If):
            raise ValueError("Editor operation chain has a non-branch else clause")
        current = current.orelse[0]
    return branches


def _pack_if_branches(
    branches: list[tuple[ast.expr, list[ast.stmt]]],
    *,
    target_lines: int,
) -> list[list[tuple[ast.expr, list[ast.stmt]]]]:
    groups: list[list[tuple[ast.expr, list[ast.stmt]]]] = []
    current: list[tuple[ast.expr, list[ast.stmt]]] = []
    size = 0
    for test, body in branches:
        branch_end = max(
            [
                int(getattr(test, "end_lineno", test.lineno) or test.lineno),
                *(int(statement.end_lineno or statement.lineno) for statement in body),
            ]
        )
        branch_size = branch_end - int(test.lineno) + 1
        if current and size + branch_size > target_lines:
            groups.append(current)
            current = []
            size = 0
        current.append((test, body))
        size += branch_size
    if current:
        groups.append(current)
    return groups


def _build_if_chain(branches: list[tuple[ast.expr, list[ast.stmt]]]) -> ast.If:
    fallback: list[ast.stmt] = [ast.Return(value=ast.Constant(value=False))]
    for test, body in reversed(branches):
        fallback = [
            ast.If(
                test=copy.deepcopy(test),
                body=[*copy.deepcopy(body), ast.Return(value=ast.Constant(value=True))],
                orelse=fallback,
            )
        ]
    return ast.fix_missing_locations(fallback[0])


def main() -> int:
    parser = argparse.ArgumentParser(description="Split the remaining oversized v14 application and domain functions.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = split_active_functions(Path(args.repo_root).resolve(), write=args.write)
    print(result)
    return 0 if not result["skipped"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
