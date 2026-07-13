from __future__ import annotations

import json
from pathlib import Path

from song_agent import __version__
from song_agent.capabilities.registry import CapabilityRegistry, CapabilitySpec, RuntimeVerificationSpec
from song_agent.ga_readiness import REQUIRED_DOCS, build_ga_readiness_report, write_ga_readiness_report
from song_agent.ga_readiness_verifier import verify_ga_readiness_report
from song_agent.platform.contracts.policy import (
    CurrentGenerationRequirement,
    EvidenceRequirement,
    NoBlockerRequirement,
    PolicyProfile,
    RuntimeVerificationRequirement,
)
from song_agent.platform.evidence_graph import build_evidence_graph
from song_agent.platform.evidence_graph.builder import write_evidence_graph_manifest
from song_agent.platform.policy import evaluate_policy
from song_agent.platform.verification.hashing import integrity_hash, sha256_file
from song_agent.projectio import write_json
from song_agent.interfaces.api.routes.delivery import DeliveryRoutes


FAKE_VERIFICATION_PACKAGE_TYPE = "musicforge_test_evidence_verification"


def fake_runtime_verifier(package_path: Path | str, *, strict: bool = False) -> dict:
    target = Path(package_path)
    fingerprint = sha256_file(target)
    report = {
        "package_type": FAKE_VERIFICATION_PACKAGE_TYPE,
        "status": "passed" if target.is_file() else "failed",
        "zip_sha256": fingerprint,
        "zip_size_bytes": target.stat().st_size if target.is_file() else 0,
        "manifest_hash": fingerprint,
        "summary": {"status": "passed", "generation": 1},
        "blockers": [],
    }
    report["integrity_hash"] = integrity_hash(report)
    return report


def _registry(component_type: str = "unified_release_program") -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register(
        CapabilitySpec(
            capability_id="test.runtime_evidence",
            component_type=component_type,
            bounded_context="test",
            application_service="test.verify",
            runtime=RuntimeVerificationSpec(
                module=__name__,
                function="fake_runtime_verifier",
                package_type="musicforge_test_evidence",
                verification_package_type=FAKE_VERIFICATION_PACKAGE_TYPE,
                defaults=(("strict", True),),
            ),
        )
    )
    return registry


def _fixture(tmp_path: Path, *, component_type: str = "unified_release_program") -> tuple[Path, Path, Path]:
    package_path = tmp_path / "evidence.zip"
    package_path.write_bytes(b"runtime evidence v1")
    report_path = tmp_path / "verification-report.json"
    write_json(report_path, fake_runtime_verifier(package_path, strict=True))
    manifest_path = tmp_path / "evidence-manifest.json"
    write_evidence_graph_manifest(
        manifest_path,
        items=[
            {
                "component_type": component_type,
                "component_id": "component-001",
                "evidence_type": "signed_archive",
                "generation": 1,
                "package_path": package_path.name,
                "verification_report_path": report_path.name,
            }
        ],
    )
    return package_path, report_path, manifest_path


def test_evidence_graph_runtime_verifies_and_omits_local_paths(tmp_path: Path) -> None:
    _package, _report, manifest = _fixture(tmp_path)

    graph = build_evidence_graph(manifest, registry=_registry())
    gate = evaluate_policy(
        PolicyProfile(
            policy_id="test",
            description="test",
            evidence_requirements=(EvidenceRequirement("root", component_types=("unified_release_program",)),),
        ),
        graph,
    )

    assert graph.status == "passed"
    assert gate.status == "passed"
    serialized = json.dumps(graph.to_dict(), ensure_ascii=False)
    assert str(tmp_path) not in serialized
    assert "package_path" not in serialized
    assert "verification_report_path" not in serialized


def test_evidence_graph_rejects_stale_report_after_package_tamper(tmp_path: Path) -> None:
    package, _report, manifest = _fixture(tmp_path)
    baseline = build_evidence_graph(manifest, registry=_registry())
    package.write_bytes(b"runtime evidence tampered")

    tampered = build_evidence_graph(manifest, registry=_registry())

    assert baseline.status == "passed"
    assert tampered.status == "failed"
    assert "evidence_verification_zip_sha256" in tampered.nodes[0].blockers


def test_evidence_graph_treats_package_directory_as_failed_evidence(tmp_path: Path) -> None:
    package, _report, manifest = _fixture(tmp_path)
    package.unlink()
    package.mkdir()

    graph = build_evidence_graph(manifest, registry=_registry())

    assert graph.status == "failed"
    assert "evidence_package_missing" in graph.nodes[0].blockers


def test_evidence_graph_rejects_duplicate_identity_and_report_reuse(tmp_path: Path) -> None:
    package, report, manifest = _fixture(tmp_path)
    write_evidence_graph_manifest(
        manifest,
        items=[
            {"component_type": "unified_release_program", "component_id": "one", "evidence_type": "archive", "package_path": package.name, "verification_report_path": report.name},
            {"component_type": "unified_release_program", "component_id": "two", "evidence_type": "archive", "package_path": package.name, "verification_report_path": report.name},
        ],
    )

    graph = build_evidence_graph(manifest, registry=_registry())

    assert graph.status == "failed"
    assert any(item.startswith("evidence_report_reused:") for item in graph.blockers)
    assert any(item.startswith("evidence_report_hash_reused:") for item in graph.blockers)


def test_evidence_graph_rejects_dependency_cycle_and_spoofed_node_id(tmp_path: Path) -> None:
    package, report, manifest = _fixture(tmp_path)
    one = "unified_release_program:one:archive:1"
    two = "unified_release_program:two:archive:1"
    write_evidence_graph_manifest(
        manifest,
        items=[
            {"node_id": "spoofed", "component_type": "unified_release_program", "component_id": "one", "evidence_type": "archive", "package_path": package.name, "verification_report_path": report.name, "dependencies": [two]},
            {"component_type": "unified_release_program", "component_id": "two", "evidence_type": "archive", "package_path": package.name, "verification_report_path": report.name, "dependencies": [one]},
        ],
    )

    graph = build_evidence_graph(manifest, registry=_registry())

    assert "evidence_dependency_cycle" in graph.blockers
    assert "evidence_node_id_identity" in graph.nodes[0].blockers


def test_policy_hard_runtime_current_and_blocker_requirements_cannot_be_disabled(tmp_path: Path) -> None:
    package, _report, manifest = _fixture(tmp_path)
    package.write_bytes(b"tampered")
    graph = build_evidence_graph(manifest, registry=_registry())
    profile = PolicyProfile(
        policy_id="cannot-disable",
        description="hard requirements remain enabled",
        current_generation=CurrentGenerationRequirement(required=False),
        runtime_verification=RuntimeVerificationRequirement(required=False),
        no_blockers=NoBlockerRequirement(required=False),
    )

    gate = evaluate_policy(profile, graph)

    assert gate.status == "failed"
    assert any(item.endswith(".current") for item in gate.blockers)
    assert any(item.endswith(".blockers") for item in gate.blockers)


def test_ga_policy_report_and_verifier_recheck_current_external_package(tmp_path: Path, monkeypatch) -> None:
    import song_agent.capabilities as capabilities

    package, _report, manifest = _fixture(tmp_path)
    monkeypatch.setattr(capabilities, "capability_registry", _registry())
    _write_repo(tmp_path)
    ga_report = build_ga_readiness_report(repo_root=tmp_path, policy="ga.standard", evidence_manifest_path=manifest)
    report_path = tmp_path / "ga-readiness.json"
    write_ga_readiness_report(ga_report, report_path)

    baseline = verify_ga_readiness_report(report_path, policy="ga.standard", evidence_manifest_path=manifest)
    implicit_policy = verify_ga_readiness_report(report_path, evidence_manifest_path=manifest)
    package.write_bytes(b"tampered after GA report")
    stale = verify_ga_readiness_report(report_path, policy="ga.standard", evidence_manifest_path=manifest)

    assert _status(baseline, "ga_readiness_evidence_policy_status") == "passed"
    assert _status(baseline, "ga_readiness_evidence_policy_binding") == "passed"
    assert _status(implicit_policy, "ga_readiness_policy_argument_required") == "failed"
    assert implicit_policy["status"] == "failed"
    assert _status(stale, "ga_readiness_evidence_policy_status") == "failed"
    assert stale["status"] == "failed"


def test_release_policy_gate_is_runtime_bound_and_force_independent(tmp_path: Path, monkeypatch) -> None:
    import song_agent.application.evidence_policy_gate as policy_gate_module

    workspace = tmp_path / ".musicforge"
    manifest_root = workspace / "evidence-manifests"
    manifest_root.mkdir(parents=True)
    package, report, source_manifest = _fixture(manifest_root, component_type="release")
    policy_manifest = manifest_root / "release-policy.json"
    source_manifest.replace(policy_manifest)
    monkeypatch.setattr(policy_gate_module, "capability_registry", _registry("release"))
    fake_routes = type("Routes", (), {"release_store": type("Store", (), {"root": workspace / "releases"})()})()

    baseline = DeliveryRoutes._release_declarative_policy_gate(
        fake_routes,
        {"policy": "release.standard", "evidence_manifest_id": "release-policy", "force": True},
    )
    package.write_bytes(b"tampered release evidence")
    stale = DeliveryRoutes._release_declarative_policy_gate(
        fake_routes,
        {"policy": "release.standard", "evidence_manifest_id": "release-policy", "force": True},
    )

    assert baseline and baseline["status"] == "passed"
    assert stale and stale["status"] == "failed"
    assert stale["hard_block"] is True
    assert report.exists()


def test_release_policy_gate_rejects_manifest_outside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / ".musicforge"
    workspace.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    fake_routes = type("Routes", (), {"release_store": type("Store", (), {"root": workspace / "releases"})()})()

    gate = DeliveryRoutes._release_declarative_policy_gate(
        fake_routes,
        {"policy": "release.standard", "evidence_manifest": str(outside)},
    )

    assert gate and gate["status"] == "failed"
    assert gate["hard_block"] is True


def test_builtin_program_capability_rechecks_real_program_package(tmp_path: Path) -> None:
    from song_agent.capabilities import capability_registry
    from tests.test_unified_release_program import _program_with_handoff

    store, program_id, external_manifest, _handoff = _program_with_handoff(tmp_path)
    store.refresh_report(program_id, {"external_evidence_manifest": external_manifest})
    store.signoff(program_id, {"external_evidence_manifest": external_manifest, "signed_by": "policy owner"})
    zipped = store.build_zip(program_id)
    external = store.verify_package(
        program_id,
        {
            "strict": True,
            "require_current": True,
            "require_signed": True,
            "external_evidence_manifest": external_manifest,
            "program_signoff_binding": store.signoff_binding_path(program_id),
        },
    )
    assert external["status"] == "passed"
    manifest = tmp_path / "program-policy-manifest.json"
    write_evidence_graph_manifest(
        manifest,
        items=[
            {
                "component_type": "unified_release_program",
                "component_id": program_id,
                "evidence_type": "signed_archive",
                "package_path": zipped["zip_path"],
                "verification_report_path": store.verification_report_path(program_id),
                "proofs": {
                    "external_evidence_manifest": external_manifest,
                    "signoff_binding": store.signoff_binding_path(program_id),
                },
            }
        ],
    )

    baseline = build_evidence_graph(manifest, registry=capability_registry)
    legacy_baseline = store.gate(
        required=True,
        program_zip_path=zipped["zip_path"],
        verification_report_path=store.verification_report_path(program_id),
        external_evidence_manifest_path=external_manifest,
        program_signoff_binding_path=store.signoff_binding_path(program_id),
    )
    with Path(zipped["zip_path"]).open("ab") as handle:
        handle.write(b"tamper")
    stale = build_evidence_graph(manifest, registry=capability_registry)
    legacy_stale = store.gate(
        required=True,
        program_zip_path=zipped["zip_path"],
        verification_report_path=store.verification_report_path(program_id),
        external_evidence_manifest_path=external_manifest,
        program_signoff_binding_path=store.signoff_binding_path(program_id),
    )

    assert baseline.status == "passed", baseline.to_dict()
    assert legacy_baseline["status"] == "passed"
    assert stale.status == "failed"
    assert legacy_stale["status"] == "failed"
    assert "evidence_runtime_verification" in stale.nodes[0].blockers


def _write_repo(root: Path) -> None:
    (root / "pyproject.toml").write_text(f'[project]\nversion = "{__version__}"\n', encoding="utf-8")
    (root / "README.md").write_text("# MusicForge\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text(f"# Changelog\n\n## v{__version__}\n", encoding="utf-8")
    for relative in REQUIRED_DOCS:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# Local test document\n", encoding="utf-8")


def _status(report: dict, check_id: str) -> str | None:
    return next((row.get("status") for row in report.get("checks", []) if row.get("check_id") == check_id), None)
