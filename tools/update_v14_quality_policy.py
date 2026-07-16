from __future__ import annotations

import argparse
import json
from pathlib import Path

from song_agent.platform.verification.hashing import stable_hash
from song_agent.release_check.v14_quality import (
    active_source_tree_hash,
    build_v14_quality_policy,
    collect_mypy_metrics,
    collect_typing_metrics,
    coverage_semantic_hash,
)
from song_agent.platform.verification.hashing import sha256_text_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the v14 typing, coverage, and complexity ratchet.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--coverage-report")
    parser.add_argument("--tracked-coverage-output", default="architecture-v14-coverage.json")
    parser.add_argument("--refresh-baseline", action="store_true")
    parser.add_argument("--ratchet-mypy", action="store_true")
    parser.add_argument("--ratchet-typing", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    report = Path(args.coverage_report).resolve() if args.coverage_report else None
    path = root / "architecture-v14-quality.json"
    if path.is_file() and not args.refresh_baseline:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise RuntimeError("Existing v14 quality policy is invalid.")
    else:
        document = build_v14_quality_policy(root)
    if args.ratchet_mypy:
        _ratchet_mypy_policy(document, collect_mypy_metrics(root))
    if args.ratchet_typing:
        _ratchet_typing_policy(document, collect_typing_metrics(root))
    if report is not None:
        output = (root / args.tracked_coverage_output).resolve()
        _write_compact_coverage(report, output, root)
        document["coverage"].update(
            {
                "report_path": output.relative_to(root).as_posix(),
                "report_sha256": _text_sha256(output),
                "source_tree_hash": active_source_tree_hash(root),
            }
        )
    document["integrity_hash"] = stable_hash(
        {key: value for key, value in document.items() if key != "integrity_hash"}
    )
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "path": path.relative_to(root).as_posix(),
                "raw_dict_str_any_max": document["typing"]["raw_dict_str_any_max_count"],
                "mypy_error_budget": document["mypy"]["max_total_errors"],
                "module_debt_count": len(document["module_size_debt"]),
                "coverage_bound": bool(document["coverage"]["report_sha256"]),
            },
            sort_keys=True,
        )
    )
    return 0


def _ratchet_mypy_policy(document: dict[str, object], metrics: dict[str, object]) -> None:
    policy = document.get("mypy")
    if not isinstance(policy, dict):
        raise RuntimeError("Existing v14 mypy policy is invalid.")
    current = int(metrics.get("total_errors") or 0)
    maximum = int(policy.get("max_total_errors") or 0)
    if metrics.get("status") != "measured" or metrics.get("strict_status") != "passed":
        raise RuntimeError("Mypy ownership cannot be ratcheted unless both measurements are valid.")
    if current > maximum:
        raise RuntimeError(f"Mypy ownership cannot grow: {current}>{maximum}.")
    budgets = metrics.get("error_budgets")
    if not isinstance(budgets, dict):
        raise RuntimeError("Measured mypy error budgets are invalid.")
    policy["max_total_errors"] = current
    policy["error_budgets"] = dict(sorted((str(key), int(value)) for key, value in budgets.items()))


def _ratchet_typing_policy(document: dict[str, object], metrics: dict[str, object]) -> None:
    policy = document.get("typing")
    if not isinstance(policy, dict):
        raise RuntimeError("Existing v14 typing policy is invalid.")
    raw = int(metrics.get("raw_dict_str_any_count") or 0)
    implementation = int(metrics.get("implementation_document_count") or 0)
    previous_raw = int(policy.get("raw_dict_str_any_max_count") or 0)
    previous_implementation = int(policy.get("implementation_document_max_count") or 0)
    if int(metrics.get("public_implementation_document_count") or 0) != 0:
        raise RuntimeError("Typing ownership cannot expose implementation documents publicly.")
    if int(metrics.get("untyped_public_function_count") or 0) != 0:
        raise RuntimeError("Typing ownership cannot introduce untyped public functions.")
    if raw + implementation > previous_raw + previous_implementation:
        raise RuntimeError(
            "Typing ownership cannot grow: "
            f"{raw + implementation}>{previous_raw + previous_implementation}."
        )
    policy["raw_dict_str_any_max_count"] = raw
    policy["implementation_document_max_count"] = implementation


def _write_compact_coverage(source: Path, target: Path, root: Path) -> None:
    raw = json.loads(source.read_text(encoding="utf-8"))
    files = {}
    for raw_path, row in (raw.get("files") or {}).items():
        path = Path(str(raw_path))
        if path.is_absolute():
            try:
                normalized = path.resolve().relative_to(root).as_posix()
            except ValueError as exc:
                raise RuntimeError("Coverage report contains a path outside the repository.") from exc
        else:
            normalized = str(raw_path).replace("\\", "/")
        if normalized.startswith("../") or "/../" in normalized:
            raise RuntimeError("Coverage report contains an unsafe relative path.")
        summary = row.get("summary") if isinstance(row, dict) else {}
        files[normalized] = {
            "summary": {
                "num_statements": int((summary or {}).get("num_statements") or 0),
                "covered_lines": int((summary or {}).get("covered_lines") or 0),
                "missing_lines": int((summary or {}).get("missing_lines") or 0),
            }
        }
    document = {
        "schema_version": 2,
        "package_type": "musicforge_v14_coverage_evidence",
        "source_report_semantic_hash": coverage_semantic_hash(files),
        "file_count": len(files),
        "files": dict(sorted(files.items())),
    }
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _text_sha256(path: Path) -> str:
    value = sha256_text_file(path)
    if value is None:
        raise FileNotFoundError(path)
    return value


if __name__ == "__main__":
    raise SystemExit(main())
