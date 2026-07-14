from __future__ import annotations

import ast
from pathlib import Path


def migrate(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    target_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name in {"ReleaseSignoffApplication", "LegacyReleaseSignoffAdapter"}
    )
    method = next(node for node in target_class.body if isinstance(node, ast.FunctionDef) and node.name == "execute")
    existing_policy = next(
        (
            node
            for node in method.body
            if isinstance(node, ast.If) and "policy_decision" in ast.unparse(node.test)
        ),
        None,
    )
    if existing_policy is not None:
        qa_gate = next(
            node
            for node in method.body
            if isinstance(node, ast.If)
            and node.lineno > existing_policy.lineno
            and "release_qa_allows_signoff" in ast.unparse(node.test)
        )
        lines = source.splitlines()
        document = "\n".join(
            [
                *lines[: int(existing_policy.end_lineno or existing_policy.lineno)],
                *lines[qa_gate.lineno - 1 :],
            ]
        ) + "\n"
        ast.parse(document, filename=str(path))
        path.write_text(document, encoding="utf-8")
        return
    first = next(node for node in method.body if node.lineno >= 590 and isinstance(node, ast.If))
    last = next(
        node
        for node in method.body
        if isinstance(node, ast.If)
        and node.lineno > first.lineno
        and _calls_get_on(node.test, "acceptance_gate", "status")
    )
    replacement = """policy_decision = evaluate_legacy_release_policy(
    payload,
    acceptance_gate,
    release_id=release_id,
    qa_passed=release_qa_allows_signoff(report) or force,
)
acceptance_gate["policy_gate"] = policy_decision
acceptance_gate["legacy_require_summary"] = policy_decision["legacy_require_summary"]
acceptance_gate["status"] = policy_decision["status"]
if policy_decision["status"] != "passed":
    self._send_error(HTTPStatus.CONFLICT, "Release Evidence Policy gate failed.")
    return"""
    lines = source.splitlines()
    updated = [
        *lines[: first.lineno - 1],
        *[(" " * 8) + line if line else "" for line in replacement.splitlines()],
        *lines[int(last.end_lineno or last.lineno) :],
    ]
    document = "\n".join(updated) + "\n"
    document = document.replace("class ReleaseSignoffApplication:", "class LegacyReleaseSignoffAdapter:", 1)
    marker = "from typing import Any\n"
    document = document.replace(
        marker,
        marker + "\nfrom song_agent.application.policy_compatibility import evaluate_legacy_release_policy\n",
        1,
    )
    ast.parse(document, filename=str(path))
    path.write_text(document, encoding="utf-8")


def _calls_get_on(node: ast.AST, variable: str, argument: str) -> bool:
    return any(
        isinstance(item, ast.Call)
        and isinstance(item.func, ast.Attribute)
        and item.func.attr == "get"
        and isinstance(item.func.value, ast.Name)
        and item.func.value.id == variable
        and bool(item.args)
        and isinstance(item.args[0], ast.Constant)
        and item.args[0].value == argument
        for item in ast.walk(node)
    )


if __name__ == "__main__":
    migrate(Path("song_agent/application/legacy/release_signoff.py"))
