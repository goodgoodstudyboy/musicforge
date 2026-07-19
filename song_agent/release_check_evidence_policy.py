from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument
import json
import tempfile
from pathlib import Path

from song_agent.capabilities import CapabilityRegistry, CapabilitySpec, RuntimeVerificationSpec, capability_registry
from song_agent.platform.evidence_graph import build_evidence_graph
from song_agent.platform.evidence_graph.builder import write_evidence_graph_manifest
from song_agent.platform.policy import evaluate_policy, get_policy_profile
from song_agent.platform.verification.hashing import integrity_hash, sha256_file
from song_agent.projectio import write_json


_SMOKE_VERIFICATION_TYPE = "musicforge_v1219_smoke_verification"


def _smoke_capability(component_type: str = "release") -> CapabilitySpec:
    return CapabilitySpec(
        capability_id=f"{component_type}.policy_smoke",
        component_type=component_type,
        bounded_context="delivery",
        application_service="policy_smoke.verify",
        runtime=RuntimeVerificationSpec(
            module=__name__,
            function="_smoke_runtime_verifier",
            package_type="musicforge_v1219_smoke",
            verification_package_type=_SMOKE_VERIFICATION_TYPE,
            defaults=(("strict", True),),
        ),
        gate_policies=("ga.standard", "release.standard"),
        cli_commands=("ga-check",),
        api_routes=("/api/ga-readiness",),
        web_panel="System Health",
        release_checks=("v136.policy_gate_cutover_smoke",),
    )


def _smoke_runtime_verifier(package_path: Path | str, *, strict: bool = False) -> ImplementationDocument:
    target = Path(package_path)
    fingerprint = sha256_file(target)
    report = {
        "package_type": _SMOKE_VERIFICATION_TYPE,
        "status": "passed" if target.is_file() else "failed",
        "zip_sha256": fingerprint,
        "zip_size_bytes": target.stat().st_size if target.is_file() else 0,
        "manifest_hash": fingerprint,
        "summary": {
            "status": "passed",
            "component_id": "release-001",
            "generation": 1,
            "current_generation": 1,
            "current": True,
            "source_hash": fingerprint,
        },
        "blockers": [],
    }
    report["integrity_hash"] = integrity_hash(report)
    return report


def run_evidence_policy_smoke(root: Path) -> tuple[bool, str]:
    del root
    try:
        registry = CapabilityRegistry()
        registry.register(_smoke_capability())
        with tempfile.TemporaryDirectory(prefix="musicforge-v1219-") as raw:
            work = Path(raw)
            package = work / "release.zip"
            package.write_bytes(b"v12.19 evidence")
            report_path = work / "verification-report.json"
            write_json(report_path, _smoke_runtime_verifier(package, strict=True))
            manifest = work / "evidence-manifest.json"
            item = {
                "component_type": "release",
                "component_id": "release-001",
                "evidence_type": "signed_archive",
                "generation": 1,
                "package_path": package.name,
                "verification_report_path": report_path.name,
            }
            write_evidence_graph_manifest(manifest, items=[item])
            graph = build_evidence_graph(manifest, registry=registry)
            baseline = evaluate_policy(get_policy_profile("release.standard"), graph)
            public_graph = json.dumps(graph.to_dict(), ensure_ascii=False)

            package.write_bytes(b"v12.19 tampered evidence")
            stale_graph = build_evidence_graph(manifest, registry=registry)
            stale = evaluate_policy(get_policy_profile("release.standard"), stale_graph)

            package.write_bytes(b"v12.19 evidence")
            duplicate = work / "duplicate.json"
            write_evidence_graph_manifest(
                duplicate,
                items=[
                    item,
                    {**item, "component_id": "release-002"},
                ],
            )
            duplicate_graph = build_evidence_graph(duplicate, registry=registry)
            inventory = capability_registry.inventory()
            checks = {
                "baseline": baseline.status == "passed",
                "runtime_tamper": stale.status == "failed" and "evidence_verification_zip_sha256" in stale_graph.nodes[0].blockers,
                "duplicate_report": any(value.startswith("evidence_report_reused:") for value in duplicate_graph.blockers),
                "path_redaction": str(work) not in public_graph and "package_path" not in public_graph,
                "capabilities_unique": len(inventory) == len({row["capability_id"] for row in inventory}),
                "profiles": all(
                    get_policy_profile(policy_id).policy_id == policy_id
                    for policy_id in (
                        "release.standard",
                        "release.audio_strict",
                        "distribution.standard",
                        "ga.standard",
                        "ga.lts",
                        "program.handoff",
                        "program.continuity",
                        "program.receiver_acceptance",
                        "release.audio",
                    )
                ),
            }
        return all(checks.values()), "v12.19 evidence policy: " + ", ".join(f"{key}={value}" for key, value in checks.items())
    except Exception as exc:
        return False, f"v12.19 evidence policy failed: {exc}"


def run_policy_gate_cutover_smoke(root: Path) -> tuple[bool, str]:
    import song_agent.capabilities as capabilities_module
    from song_agent.ga_readiness import build_ga_readiness_report

    original_registry = capabilities_module.capability_registry
    try:
        registry = CapabilityRegistry()
        registry.register(_smoke_capability("unified_release_program"))
        capabilities_module.capability_registry = registry
        with tempfile.TemporaryDirectory(prefix="musicforge-v136-") as raw:
            work = Path(raw)
            package = work / "program.zip"
            package.write_bytes(b"v13.6 policy evidence")
            report_path = work / "verification-report.json"
            write_json(report_path, _smoke_runtime_verifier(package, strict=True))
            manifest = work / "evidence-manifest.json"
            write_evidence_graph_manifest(
                manifest,
                items=[
                    {
                        "component_type": "unified_release_program",
                        "component_id": "release-001",
                        "evidence_type": "signed_archive",
                        "generation": 1,
                        "package_path": package.name,
                        "verification_report_path": report_path.name,
                    }
                ],
            )
            policy_report = build_ga_readiness_report(
                repo_root=root,
                policy="ga.standard",
                evidence_manifest_path=manifest,
            )
            legacy_alias_report = build_ga_readiness_report(
                repo_root=root,
                policy="ga.standard",
                evidence_manifest_path=manifest,
                require_manual_acceptance=True,
            )
            manifest_doc = json.loads(manifest.read_text(encoding="utf-8"))
            manifest_doc["items"][0]["component_id"] = "forged-program"
            manifest_doc["integrity_hash"] = integrity_hash(manifest_doc)
            manifest.write_text(json.dumps(manifest_doc, indent=2) + "\n", encoding="utf-8")
            forged = build_evidence_graph(manifest, registry=registry)

        inventory = capability_registry.inventory()
        required_profiles = {
            "ga.standard",
            "ga.lts",
            "release.audio",
            "program.continuity",
            "program.receiver_acceptance",
        }
        release_entry = (root / "song_agent" / "application" / "release_signoff.py").read_text(encoding="utf-8")
        release_adapter = (root / "song_agent" / "application" / "legacy" / "release_signoff.py").read_text(encoding="utf-8")
        program_core = (root / "song_agent" / "application" / "program" / "http_routes" / "core.py").read_text(encoding="utf-8")
        checks = {
            "profiles": all(get_policy_profile(value).policy_id == value for value in required_profiles),
            "capability_metadata": all(
                all(row.get(key) for key in ("cli_commands", "api_routes", "web_panel", "release_checks", "gate_policies"))
                for row in inventory
            ),
            "same_manifest_same_policy": policy_report.get("status") == legacy_alias_report.get("status") == "ready",
            "legacy_summary_non_authoritative": legacy_alias_report.get("legacy_require_summary", {}).get("authoritative") is False,
            "identity_tamper": forged.status == "failed" and "evidence_manifest_identity_component_id" in forged.nodes[0].blockers,
            "release_entry_thin": len(release_entry.splitlines()) < 20 and 'payload.get("require_' not in release_entry and "LegacyReleaseSignoffAdapter" in release_entry,
            "release_adapter_policy_owned": "evaluate_legacy_release_policy" in release_adapter,
            "program_policy_owned": "service.evaluate_gate" in program_core,
        }
        return all(checks.values()), "v13.6 policy cutover: " + ", ".join(f"{key}={value}" for key, value in checks.items())
    except Exception as exc:
        return False, f"v13.6 policy cutover failed: {exc}"
    finally:
        capabilities_module.capability_registry = original_registry
