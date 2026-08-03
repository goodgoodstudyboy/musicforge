from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast


WAVE0_CHANGED_SOURCES = (
    "song_agent/capabilities/model.py",
    "song_agent/domains/program/unified_command_center_evidence_review.py",
    "song_agent/domains/program/unified_command_center_evidence_review_verifier.py",
    "song_agent/domains/program/unified_command_center_release_train.py",
    "song_agent/domains/program/unified_command_center_verifier.py",
    "song_agent/domains/program/unified_release_program_continuity_acceptance.py",
    "song_agent/domains/program/unified_release_program_continuity_command_center_acceptance.py",
    "song_agent/domains/program/unified_release_program_continuity_command_center_acceptance_change.py",
    "song_agent/domains/program/unified_release_program_handoff.py",
    "song_agent/domains/program/unified_release_program_handoff_verifier.py",
    "song_agent/domains/quality/audio_campaign_governance.py",
    "song_agent/domains/quality/release_audio_command_center.py",
    "song_agent/domains/quality/release_audio_command_center_verifier.py",
    "song_agent/domains/trust/public_trust_center.py",
    "song_agent/domains/trust/release_portfolio_governance_evidence_vault.py",
    "song_agent/domains/trust/trust_operations_continuous_assurance.py",
    "song_agent/domains/trust/trust_operations_continuous_assurance_verifier.py",
    "song_agent/domains/trust/trust_operations_final_readiness.py",
    "song_agent/domains/trust/trust_operations_hub.py",
    "song_agent/interfaces/api/routes/trust_parts/public_trust_center_acceptance_board.py",
    "song_agent/interfaces/api/routes/trust_parts/public_trust_centers.py",
    "song_agent/interfaces/api/server.py",
    "song_agent/interfaces/cli/commands/delivery_parts/verify_release.py",
    "song_agent/interfaces/cli/commands/delivery_parts/verify_unified_release_program_operations.py",
    "song_agent/interfaces/cli/commands/maintenance_parts/maintenance_commands_and_presenter_adapters.py",
    "song_agent/interfaces/cli/commands/quality_parts/verify_release_audio_quality_observatory.py",
    "song_agent/interfaces/cli/commands/trust_parts/public_trust_center_publication_store.py",
    "song_agent/interfaces/cli/commands/trust_parts/verify_public_trust_center_distribution_kit.py",
    "song_agent/interfaces/cli/commands/trust_parts/verify_release_portfolio_governance_attestation_portal.py",
    "song_agent/interfaces/cli/commands/trust_parts/verify_trust_operations_assurance_watch.py",
    "song_agent/platform/contracts/__init__.py",
    "song_agent/platform/contracts/packages.py",
    "song_agent/platform/evidence_graph/builder.py",
    "song_agent/platform/lifecycle/generation.py",
    "song_agent/platform/persistence/file_artifacts.py",
    "song_agent/platform/persistence/repository.py",
    "song_agent/platform/verification/attack_corpus.py",
    "song_agent/platform/verification/model.py",
    "song_agent/release_check/checks/meta.py",
    "song_agent/release_check/matrix.py",
    "song_agent/release_check/v14_quality.py",
    "song_agent/release_check/v14_wave0.py",
    "song_agent/release_check/v14_wave0_catalog_model.py",
    "song_agent/release_check/v14_wave0_inventory.py",
    "song_agent/release_check/v14_wave0_package_effects.py",
    "song_agent/release_check/v14_wave0_package_inventory.py",
    "song_agent/release_check/v14_wave0_package_registry.py",
    "song_agent/release_check/v14_wave0_package_scan.py",
    "song_agent/release_check/v14_wave0_ratchet.py",
    "song_agent/release_check/v14_wave0_registry.py",
    "song_agent/release_check/v14_wave0_source.py",
    "song_agent/release_check/v14_wave0_state_registry.py",
    "song_agent/release_check/v14_wave0_surfaces.py",
    "song_agent/release_check_verification_kernel.py",
)


def merge_coverage_reports(base: dict[str, object], overlay: dict[str, object]) -> dict[str, object]:
    base_files = _normalized_files(base)
    overlay_files = _normalized_files(overlay)
    missing = sorted(set(WAVE0_CHANGED_SOURCES) - set(overlay_files))
    if missing:
        raise ValueError(f"Wave 0 coverage is missing changed sources: {missing}")
    for path in WAVE0_CHANGED_SOURCES:
        base_files[path] = overlay_files[path]
    totals = _totals(base_files)
    return {
        "meta": dict(cast(dict[str, object], overlay.get("meta") or {})),
        "files": dict(sorted(base_files.items())),
        "totals": totals,
    }


def _normalized_files(document: dict[str, object]) -> dict[str, dict[str, object]]:
    files = cast(dict[str, object], document.get("files") or {})
    return {str(path).replace("\\", "/"): cast(dict[str, object], row) for path, row in files.items() if isinstance(row, dict)}


def _totals(files: dict[str, dict[str, object]]) -> dict[str, object]:
    covered = 0
    statements = 0
    missing = 0
    excluded = 0
    for row in files.values():
        summary = cast(dict[str, object], row.get("summary") or {})
        covered += int(cast(int | str, summary.get("covered_lines") or 0))
        statements += int(cast(int | str, summary.get("num_statements") or 0))
        missing += int(cast(int | str, summary.get("missing_lines") or 0))
        excluded += int(cast(int | str, summary.get("excluded_lines") or 0))
    percent = 100.0 if statements == 0 else covered * 100.0 / statements
    return {
        "covered_lines": covered,
        "num_statements": statements,
        "percent_covered": percent,
        "percent_covered_display": str(round(percent)),
        "missing_lines": missing,
        "excluded_lines": excluded,
        "percent_statements_covered": percent,
        "percent_statements_covered_display": str(round(percent)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge v14.4 Wave 0 coverage into a full baseline.")
    parser.add_argument("base", type=Path)
    parser.add_argument("overlay", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    base = json.loads(args.base.read_text(encoding="utf-8"))
    overlay = json.loads(args.overlay.read_text(encoding="utf-8"))
    merged = merge_coverage_reports(base, overlay)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
