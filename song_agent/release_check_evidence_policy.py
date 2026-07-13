from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from song_agent.capabilities import CapabilityRegistry, CapabilitySpec, RuntimeVerificationSpec, capability_registry
from song_agent.platform.evidence_graph import build_evidence_graph
from song_agent.platform.evidence_graph.builder import write_evidence_graph_manifest
from song_agent.platform.policy import evaluate_policy, get_policy_profile
from song_agent.platform.verification.hashing import integrity_hash, sha256_file
from song_agent.projectio import write_json


_SMOKE_VERIFICATION_TYPE = "musicforge_v1219_smoke_verification"


def _smoke_runtime_verifier(package_path: Path | str, *, strict: bool = False) -> dict[str, Any]:
    target = Path(package_path)
    fingerprint = sha256_file(target)
    report = {
        "package_type": _SMOKE_VERIFICATION_TYPE,
        "status": "passed" if target.is_file() else "failed",
        "zip_sha256": fingerprint,
        "zip_size_bytes": target.stat().st_size if target.is_file() else 0,
        "manifest_hash": fingerprint,
        "summary": {"status": "passed", "generation": 1},
        "blockers": [],
    }
    report["integrity_hash"] = integrity_hash(report)
    return report


def run_evidence_policy_smoke(root: Path) -> tuple[bool, str]:
    del root
    try:
        registry = CapabilityRegistry()
        registry.register(
            CapabilitySpec(
                capability_id="release.v1219_smoke",
                component_type="release",
                bounded_context="delivery",
                application_service="release.verify",
                runtime=RuntimeVerificationSpec(
                    module=__name__,
                    function="_smoke_runtime_verifier",
                    package_type="musicforge_v1219_smoke",
                    verification_package_type=_SMOKE_VERIFICATION_TYPE,
                    defaults=(("strict", True),),
                ),
            )
        )
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
                    )
                ),
            }
        return all(checks.values()), "v12.19 evidence policy: " + ", ".join(f"{key}={value}" for key, value in checks.items())
    except Exception as exc:
        return False, f"v12.19 evidence policy failed: {exc}"
