from __future__ import annotations

import ast
from pathlib import Path

from migrate_v14_domains import _module_exports, _rewrite_imports


SOURCE = Path("song_agent/domains/studio/projects.py")
REPOSITORY = Path("song_agent/domains/studio/project_repository.py")
ENRICHMENT = Path("song_agent/domains/studio/project_export_enrichment.py")
MOVED_FUNCTIONS = (
    "_collect_project_review_tasks",
    "_project_version_song_plan",
    "_collect_project_review_sprints",
    "_collect_project_review_metrics_summary",
    "_collect_project_acceptance_fix_sprint_summary",
    "_collect_project_acceptance_fix_plan_summary",
    "_collect_project_acceptance_fix_plan_review_summary",
    "_collect_project_acceptance_kb_summary",
    "_collect_project_planning_rule_simulation_summary",
    "_collect_project_planning_rule_governance_summary",
    "_collect_project_planning_rule_impact_summary",
    "_collect_project_delivery_qa_summary",
    "_collect_project_delivery_signoff_summary",
)


def split(root: Path) -> int:
    source_path = root / SOURCE
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = sorted(set(MOVED_FUNCTIONS) - set(functions))
    if missing:
        repository_path = root / REPOSITORY
        enrichment_path = root / ENRICHMENT
        if repository_path.is_file() and enrichment_path.is_file():
            adapter = _adapter_source(
                repository_path.read_text(encoding="utf-8"),
                enrichment_path.read_text(encoding="utf-8"),
            )
            ast.parse(adapter, filename=str(SOURCE))
            source_path.write_text(adapter, encoding="utf-8")
            _rewrite_domain_callers(root)
            print("repaired project composition adapter")
            return 0
        raise ValueError("Missing project enrichment functions: " + ", ".join(missing))

    moved_source = "\n\n\n".join(
        ast.get_source_segment(source, functions[name]) or ""
        for name in MOVED_FUNCTIONS
    )
    repository = source
    start = _offset(source, functions[MOVED_FUNCTIONS[0]].lineno, functions[MOVED_FUNCTIONS[0]].col_offset)
    last = functions[MOVED_FUNCTIONS[-1]]
    end = _offset(source, int(last.end_lineno or last.lineno), int(last.end_col_offset or 0))
    repository = repository[:start] + repository[end:].lstrip("\n")
    repository = repository.replace(
        "from song_agent.domains.studio.project_planning_read_models import collect_planning_rule_governance_summary, collect_planning_rule_impact_summary, collect_planning_rule_simulation_summary\n",
        "",
    )
    repository = repository.replace(
        "class ProjectStore:\n    def __init__(self, root: Path | str = PROJECT_ROOT):\n        self.root = Path(root).resolve()\n        self.lock = threading.RLock()",
        "class ProjectStore:\n    def __init__(\n        self,\n        root: Path | str = PROJECT_ROOT,\n        *,\n        summary_provider: ProjectSummaryProvider | None = None,\n    ):\n        self.root = Path(root).resolve()\n        self.lock = threading.RLock()\n        self.summary_provider = summary_provider or _empty_project_summary",
    )
    marker = "\n\nclass ProjectStore:\n"
    protocol = (
        "\n\nclass ProjectSummaryProvider(Protocol):\n"
        "    def __call__(\n"
        "        self,\n"
        "        project_dir: Path,\n"
        "        document: ProjectDocument,\n"
        "    ) -> dict[str, Any]: ...\n"
        "\n\n"
        "def _empty_project_summary(\n"
        "    project_dir: Path,\n"
        "    document: ProjectDocument,\n"
        ") -> dict[str, Any]:\n"
        "    return {}\n"
    )
    if marker not in repository:
        raise ValueError("ProjectStore marker was not found")
    repository = repository.replace(marker, protocol + marker, 1)
    old_snapshot = '''        return {
            "project": document.state.to_dict(),
            "versions": [self._export_version(version) for version in document.versions],
            "selected_version": _version_or_none(document, document.state.selected_version_id),
            "final_version": _version_or_none(document, document.state.final_version_id),
            "asset_refs": _collect_project_asset_refs(self.project_dir(project_id), document),
            "reference_refs": _collect_project_reference_refs(self.project_dir(project_id), document),
            "context_packs": _collect_project_context_packs(self.project_dir(project_id), document),
            "review_tasks": _collect_project_review_tasks(self.project_dir(project_id)),
            "review_sprints": _collect_project_review_sprints(self.project_dir(project_id)),
            "review_metrics_summary": _collect_project_review_metrics_summary(self.project_dir(project_id)),
            "acceptance_fix_sprint_summary": _collect_project_acceptance_fix_sprint_summary(document.state.project_id),
            "acceptance_fix_plan_summary": _collect_project_acceptance_fix_plan_summary(document.state.project_id),
            "acceptance_fix_plan_review_summary": _collect_project_acceptance_fix_plan_review_summary(document.state.project_id),
            "acceptance_kb_summary": _collect_project_acceptance_kb_summary(document.state.project_id),
            "planning_rule_simulation_summary": _collect_project_planning_rule_simulation_summary(document.state.project_id),
            "planning_rule_governance_summary": _collect_project_planning_rule_governance_summary(document.state.project_id),
            "planning_rule_impact_summary": _collect_project_planning_rule_impact_summary(document.state.project_id),
            "delivery_qa_summary": _collect_project_delivery_qa_summary(self.project_dir(project_id)),
            "delivery_signoff_summary": _collect_project_delivery_signoff_summary(self.project_dir(project_id)),
            "generated_at": now_iso(),
        }'''
    new_snapshot = '''        project_dir = self.project_dir(project_id)
        snapshot = {
            "project": document.state.to_dict(),
            "versions": [self._export_version(version) for version in document.versions],
            "selected_version": _version_or_none(document, document.state.selected_version_id),
            "final_version": _version_or_none(document, document.state.final_version_id),
            "asset_refs": _collect_project_asset_refs(project_dir, document),
            "reference_refs": _collect_project_reference_refs(project_dir, document),
            "context_packs": _collect_project_context_packs(project_dir, document),
            "generated_at": now_iso(),
        }
        snapshot.update(self.summary_provider(project_dir, document))
        return snapshot'''
    if old_snapshot not in repository:
        raise ValueError("Project export snapshot block was not found")
    repository = repository.replace(old_snapshot, new_snapshot, 1)
    ast.parse(repository, filename=str(REPOSITORY))
    (root / REPOSITORY).write_text(repository, encoding="utf-8")

    enrichment = _enrichment_source(moved_source)
    ast.parse(enrichment, filename=str(ENRICHMENT))
    (root / ENRICHMENT).write_text(enrichment, encoding="utf-8")

    adapter = _adapter_source(repository, enrichment)
    ast.parse(adapter, filename=str(SOURCE))
    source_path.write_text(adapter, encoding="utf-8")
    _rewrite_domain_callers(root)
    print("split project repository and export enrichment")
    return 0


def _enrichment_source(moved_source: str) -> str:
    return f'''from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from song_agent.domains.creation.redaction import sanitize_metadata
from song_agent.domains.studio.project_planning_read_models import collect_planning_rule_governance_summary, collect_planning_rule_impact_summary, collect_planning_rule_simulation_summary
from song_agent.domains.studio.project_repository import BLOCKED_ASSET_METADATA_KEYS, ProjectDocument
from song_agent.domains.studio.projectio import read_json


def build_project_summary(project_dir: Path, document: ProjectDocument) -> dict[str, Any]:
    project_id = document.state.project_id
    return {{
        "review_tasks": _collect_project_review_tasks(project_dir),
        "review_sprints": _collect_project_review_sprints(project_dir),
        "review_metrics_summary": _collect_project_review_metrics_summary(project_dir),
        "acceptance_fix_sprint_summary": _collect_project_acceptance_fix_sprint_summary(project_id),
        "acceptance_fix_plan_summary": _collect_project_acceptance_fix_plan_summary(project_id),
        "acceptance_fix_plan_review_summary": _collect_project_acceptance_fix_plan_review_summary(project_id),
        "acceptance_kb_summary": _collect_project_acceptance_kb_summary(project_id),
        "planning_rule_simulation_summary": _collect_project_planning_rule_simulation_summary(project_id),
        "planning_rule_governance_summary": _collect_project_planning_rule_governance_summary(project_id),
        "planning_rule_impact_summary": _collect_project_planning_rule_impact_summary(project_id),
        "delivery_qa_summary": _collect_project_delivery_qa_summary(project_dir),
        "delivery_signoff_summary": _collect_project_delivery_signoff_summary(project_dir),
    }}


{moved_source}


def _sanitize_asset_metadata(value: Any) -> Any:
    return sanitize_metadata(value, blocked_keys=BLOCKED_ASSET_METADATA_KEYS)
'''


def _adapter_source(repository: str, enrichment: str) -> str:
    repository_exports = set(_module_exports(repository))
    repository_exports.discard("ProjectStore")
    enrichment_exports = set(_module_exports(enrichment))
    repository_names = sorted(repository_exports)
    enrichment_names = sorted(enrichment_exports)
    names = sorted(repository_exports | enrichment_exports)
    rows = [
        '"""Project application-facing composition over the domain repository."""\n\n',
        f"from song_agent.domains.studio.project_repository import {', '.join(repository_names)}\n",
        f"from song_agent.domains.studio.project_export_enrichment import {', '.join(enrichment_names)}\n",
        "from song_agent.domains.studio.project_repository import ProjectStore as _RepositoryProjectStore\n",
        "\n\n",
        "class ProjectStore(_RepositoryProjectStore):\n",
        "    def __init__(self, root: Path | str = PROJECT_ROOT):\n",
        "        super().__init__(root, summary_provider=build_project_summary)\n\n\n",
        f"__all__ = {tuple([*names, 'ProjectStore'])!r}\n",
    ]
    return "".join(rows)


def _rewrite_domain_callers(root: Path) -> None:
    replacements = {
        "song_agent.domains.studio.projects": "song_agent.domains.studio.project_repository"
    }
    excluded = {root / SOURCE, root / ENRICHMENT, root / REPOSITORY}
    for path in sorted((root / "song_agent" / "domains").rglob("*.py")):
        if path in excluded:
            continue
        source = path.read_text(encoding="utf-8")
        updated = _rewrite_imports(source, replacements)
        if updated != source:
            path.write_text(updated, encoding="utf-8")


def _offset(source: str, line: int, column: int) -> int:
    lines = source.splitlines(keepends=True)
    return sum(len(value) for value in lines[: line - 1]) + column


if __name__ == "__main__":
    raise SystemExit(split(Path.cwd()))
