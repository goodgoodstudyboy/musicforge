from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class TrustRoutesPart005:
    def _handle_public_trust_centers(self, method: str, path: str) -> None:
        prefix = "/api/public-trust-centers"
        tail = path[len(prefix):]
        try:
            if tail in {"", "/"}:
                if method == "GET":
                    centers = self.public_trust_center_store.list_centers()
                    self._send_json({"ok": True, "centers": centers, "summary": {"count": len(centers)}})
                    return
                if method == "POST":
                    config = self.public_trust_center_store.create_or_update_center(self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "center": config, "summary": public_trust_center_summary(self.public_trust_center_store.read_report(str(config.get("center_id") or "ptc-default"), default={}))}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            parts = [part for part in tail.strip("/").split("/") if part]
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Public Trust Center route not found.")
                return
            center_id = parts[0]
            if center_id.endswith(".zip") and len(parts) == 1:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                actual_id = center_id[:-4]
                self.public_trust_center_store.get_center(actual_id)
                self._send_file(self.public_trust_center_store.zip_path(actual_id), "application/zip", filename=f"musicforge-{actual_id}-public-trust-center.zip")
                return
            action = parts[1] if len(parts) > 1 else ""
            if len(parts) == 1:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                detail = self.public_trust_center_store.get_center(center_id)
                self._send_json({"ok": True, **detail})
                return
            if action == "refresh" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.public_trust_center_store.refresh_report(center_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, "report": report, "summary": public_trust_center_summary(report)}, status=HTTPStatus.CREATED)
                return
            if action == "export" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = self.public_trust_center_store.export_center(center_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, "manifest": manifest, "summary": {"source_hash": manifest.get("source_hash"), "package_type": manifest.get("package_type")}}, status=HTTPStatus.CREATED)
                return
            if action == "zip" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                zip_info = self.public_trust_center_store.build_zip(center_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, "zip": zip_info})
                return
            if action == "verify" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = verify_public_trust_center_package(
                    self.public_trust_center_store.zip_path(center_id),
                    strict=bool(payload.get("strict", True)),
                    require_registry_current=bool(payload.get("require_registry_current", False)),
                    require_portal_current=bool(payload.get("require_portal_current", False)),
                    require_transparency_current=bool(payload.get("require_transparency_current", False)),
                    require_acknowledgement_current=bool(payload.get("require_acknowledgement_current", False)),
                    require_release_readiness=bool(payload.get("require_release_readiness", False)),
                    require_delivery_readiness=bool(payload.get("require_delivery_readiness", False)),
                    require_distribution_ready=bool(payload.get("require_distribution_ready", False)),
                    require_submission_accepted=bool(payload.get("require_submission_accepted", False)),
                    require_submission_evidence=bool(payload.get("require_submission_evidence", False)),
                    require_operations_signed=bool(payload.get("require_operations_signed", False)),
                    require_operations_audit=bool(payload.get("require_operations_audit", False)),
                    require_operations_reviewer_pack=bool(payload.get("require_operations_reviewer_pack", False)),
                    delivery_anchor_path=self.public_trust_center_store.delivery_anchor_path(center_id),
                    anchor_registry_path=self.public_trust_center_anchor_registry_store.zip_path(center_id) if bool(payload.get("require_anchor_registry_current", False)) or bool(payload.get("require_anchor_published", False)) or bool(payload.get("require_anchor_not_revoked", False)) or bool(payload.get("use_anchor_registry", False)) else None,
                    anchor_transparency_path=self.public_trust_center_anchor_transparency_store.zip_path(center_id) if bool(payload.get("require_anchor_transparency_current", False)) or bool(payload.get("require_anchor_checkpoint", False)) or bool(payload.get("use_anchor_transparency", False)) else None,
                    anchor_checkpoint_path=self.public_trust_center_anchor_transparency_store.current_checkpoint_path(center_id) if bool(payload.get("require_anchor_checkpoint", False)) or bool(payload.get("use_anchor_transparency", False)) else None,
                    require_anchor_registry_current=bool(payload.get("require_anchor_registry_current", False)),
                    require_anchor_published=bool(payload.get("require_anchor_published", False)),
                    require_anchor_not_revoked=bool(payload.get("require_anchor_not_revoked", False)),
                    require_anchor_transparency_current=bool(payload.get("require_anchor_transparency_current", False)),
                    require_anchor_checkpoint=bool(payload.get("require_anchor_checkpoint", False)),
                )
                write_public_trust_center_verification_report(report, self.public_trust_center_store.verification_report_path(center_id))
                self._send_json({"ok": True, "center_id": center_id, "verification": report, "summary": report.get("summary", {})})
                return
            if action == "anchor-registry":
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    registry = self.public_trust_center_anchor_registry_store.read_registry(center_id, default={})
                    report = self.public_trust_center_anchor_registry_store.read_report(center_id, default={})
                    self._send_json({"ok": True, "center_id": center_id, "registry": registry, "report": report, "summary": self.public_trust_center_anchor_registry_store.summary(center_id)})
                    return
                subaction = parts[2] if len(parts) > 2 else ""
                if subaction == "download" and len(parts) == 3:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.public_trust_center_anchor_registry_store.zip_path(center_id), "application/zip", filename=f"musicforge-{center_id}-anchor-registry.zip")
                    return
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                if subaction == "register-current" and len(parts) == 3:
                    result = self.public_trust_center_anchor_registry_store.register_current_anchor(center_id, payload, now=_utc_now())
                    status = HTTPStatus.OK if result.get("existing") else HTTPStatus.CREATED
                    self._send_json({"ok": True, "center_id": center_id, **result, "summary": public_trust_center_anchor_registry_summary(result.get("registry") if isinstance(result.get("registry"), dict) else {})}, status=status)
                    return
                if subaction == "publish" and len(parts) == 4:
                    result = self.public_trust_center_anchor_registry_store.publish_entry(center_id, parts[3], payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, **result, "summary": public_trust_center_anchor_registry_summary(result.get("registry") if isinstance(result.get("registry"), dict) else {})})
                    return
                if subaction == "revoke" and len(parts) == 4:
                    result = self.public_trust_center_anchor_registry_store.revoke_entry(center_id, parts[3], payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, **result, "summary": public_trust_center_anchor_registry_summary(result.get("registry") if isinstance(result.get("registry"), dict) else {})})
                    return
                if subaction == "supersede" and len(parts) == 4:
                    result = self.public_trust_center_anchor_registry_store.supersede_entry(center_id, parts[3], payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, **result, "summary": public_trust_center_anchor_registry_summary(result.get("registry") if isinstance(result.get("registry"), dict) else {})})
                    return
                if subaction == "refresh" and len(parts) == 3:
                    report = self.public_trust_center_anchor_registry_store.refresh_report(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "report": report, "summary": public_trust_center_anchor_registry_summary(self.public_trust_center_anchor_registry_store.read_registry(center_id, default={}))}, status=HTTPStatus.CREATED)
                    return
                if subaction == "export" and len(parts) == 3:
                    manifest = self.public_trust_center_anchor_registry_store.export_registry(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "manifest": manifest, "summary": {"source_hash": manifest.get("source_hash"), "package_type": manifest.get("package_type")}}, status=HTTPStatus.CREATED)
                    return
                if subaction == "zip" and len(parts) == 3:
                    zip_info = self.public_trust_center_anchor_registry_store.build_zip(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "zip": zip_info})
                    return
                if subaction == "verify" and len(parts) == 3:
                    report = verify_public_trust_center_anchor_registry_package(
                        self.public_trust_center_anchor_registry_store.zip_path(center_id),
                        strict=bool(payload.get("strict", True)),
                        require_current=bool(payload.get("require_current", False)),
                        require_anchor_published=bool(payload.get("require_anchor_published", False)),
                        require_anchor_not_revoked=bool(payload.get("require_anchor_not_revoked", False)),
                    )
                    write_public_trust_center_anchor_registry_verification_report(report, self.public_trust_center_anchor_registry_store.verification_report_path(center_id))
                    self._send_json({"ok": True, "center_id": center_id, "verification": report, "summary": report.get("summary", {})})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Public Trust Center Anchor Registry route not found.")
                return
            if action == "anchor-transparency":
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.public_trust_center_anchor_transparency_store.read_report(center_id, default={})
                    checkpoint = self.public_trust_center_anchor_transparency_store.read_checkpoint(center_id, default={})
                    self._send_json({"ok": True, "center_id": center_id, "report": report, "checkpoint": checkpoint, "summary": self.public_trust_center_anchor_transparency_store.summary(center_id)})
                    return
                subaction = parts[2] if len(parts) > 2 else ""
                if subaction == "download" and len(parts) == 3:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.public_trust_center_anchor_transparency_store.zip_path(center_id), "application/zip", filename=f"musicforge-{center_id}-anchor-transparency.zip")
                    return
                if subaction == "checkpoint" and len(parts) == 3:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.public_trust_center_anchor_transparency_store.current_checkpoint_path(center_id), "application/json", filename=f"musicforge-{center_id}-anchor-checkpoint.json")
                    return
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                if subaction == "refresh" and len(parts) == 3:
                    report = self.public_trust_center_anchor_transparency_store.refresh_report(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "report": report, "summary": public_trust_center_anchor_transparency_summary(report)}, status=HTTPStatus.CREATED)
                    return
                if subaction == "checkpoint" and len(parts) == 4 and parts[3] == "create":
                    checkpoint = self.public_trust_center_anchor_transparency_store.create_checkpoint(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "checkpoint": checkpoint}, status=HTTPStatus.CREATED)
                    return
                if subaction == "export" and len(parts) == 3:
                    manifest = self.public_trust_center_anchor_transparency_store.export_transparency(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "manifest": manifest, "summary": {"source_hash": manifest.get("source_hash"), "package_type": manifest.get("package_type")}}, status=HTTPStatus.CREATED)
                    return
                if subaction == "zip" and len(parts) == 3:
                    zip_info = self.public_trust_center_anchor_transparency_store.build_zip(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "zip": zip_info})
                    return
                if subaction == "verify" and len(parts) == 3:
                    report = verify_public_trust_center_anchor_transparency_package(
                        self.public_trust_center_anchor_transparency_store.zip_path(center_id),
                        strict=bool(payload.get("strict", True)),
                        checkpoint_path=self.public_trust_center_anchor_transparency_store.current_checkpoint_path(center_id) if bool(payload.get("require_current_checkpoint", False)) or bool(payload.get("use_checkpoint", False)) else None,
                        anchor_registry_path=self.public_trust_center_anchor_registry_store.zip_path(center_id) if bool(payload.get("use_anchor_registry", False)) or bool(payload.get("require_published_anchor", False)) or bool(payload.get("require_not_revoked", False)) else None,
                        require_current_checkpoint=bool(payload.get("require_current_checkpoint", False)),
                        require_published_anchor=bool(payload.get("require_published_anchor", False)),
                        require_not_revoked=bool(payload.get("require_not_revoked", False)),
                    )
                    write_public_trust_center_anchor_transparency_verification_report(report, self.public_trust_center_anchor_transparency_store.verification_report_path(center_id))
                    self._send_json({"ok": True, "center_id": center_id, "verification": report, "summary": report.get("summary", {})})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Public Trust Center Anchor Transparency route not found.")
                return
            if action == "distribution-kit":
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.public_trust_center_distribution_kit_store.read_report(center_id, default={})
                    self._send_json({"ok": True, "center_id": center_id, "report": report, "summary": self.public_trust_center_distribution_kit_store.summary(center_id)})
                    return
                subaction = parts[2] if len(parts) > 2 else ""
                if subaction == "acceptance":
                    self._handle_public_trust_center_distribution_kit_acceptance(method, center_id, parts)
                    return
                if subaction == "download" and len(parts) == 3:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.public_trust_center_distribution_kit_store.zip_path(center_id), "application/zip", filename=f"musicforge-{center_id}-distribution-kit.zip")
                    return
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                if subaction == "refresh" and len(parts) == 3:
                    report = self.public_trust_center_distribution_kit_store.refresh_report(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "report": report, "summary": public_trust_center_distribution_kit_summary(report)}, status=HTTPStatus.CREATED)
                    return
                if subaction == "export" and len(parts) == 3:
                    manifest = self.public_trust_center_distribution_kit_store.export_kit(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "manifest": manifest, "summary": {"source_hash": manifest.get("source_hash"), "package_type": manifest.get("package_type")}}, status=HTTPStatus.CREATED)
                    return
                if subaction == "zip" and len(parts) == 3:
                    zip_info = self.public_trust_center_distribution_kit_store.build_zip(center_id, payload, now=_utc_now())
                    self._send_json({"ok": True, "center_id": center_id, "zip": zip_info})
                    return
                if subaction == "verify" and len(parts) == 3:
                    report = self.public_trust_center_distribution_kit_store.verify_zip(
                        center_id,
                        {
                            "strict": bool(payload.get("strict", True)),
                            "deep": bool(payload.get("deep", True)),
                            "require_current": bool(payload.get("require_current", True)),
                            "require_delivery_readiness": bool(payload.get("require_delivery_readiness", True)),
                            "require_anchor_registry_current": bool(payload.get("require_anchor_registry_current", True)),
                            "require_anchor_published": bool(payload.get("require_anchor_published", True)),
                            "require_anchor_not_revoked": bool(payload.get("require_anchor_not_revoked", True)),
                            "require_anchor_transparency_current": bool(payload.get("require_anchor_transparency_current", True)),
                            "require_anchor_checkpoint": bool(payload.get("require_anchor_checkpoint", True)),
                        },
                        now=_utc_now(),
                    )
                    self._send_json({"ok": True, "center_id": center_id, "verification": report, "summary": report.get("summary", {})})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Public Trust Center Distribution Kit route not found.")
                return
            if action == "acceptance-board":
                self._handle_public_trust_center_acceptance_board(method, center_id, parts)
                return
            if action == "archive" and len(parts) == 2:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                archive = self.public_trust_center_store.archive_snapshot(center_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "center_id": center_id, "archive": archive, "summary": {"status": "archived", "zip_sha256": archive.get("zip_sha256")}})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Public Trust Center route not found.")
        except PublicTrustCenterNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PublicTrustCenterStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PublicTrustCenterError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except PublicTrustCenterAnchorRegistryNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PublicTrustCenterAnchorRegistryStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PublicTrustCenterAnchorRegistryError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except PublicTrustCenterAnchorTransparencyNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PublicTrustCenterAnchorTransparencyStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PublicTrustCenterAnchorTransparencyError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except PublicTrustCenterDistributionKitNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PublicTrustCenterDistributionKitStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PublicTrustCenterDistributionKitError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except PublicTrustCenterDistributionKitAcceptanceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PublicTrustCenterDistributionKitAcceptanceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PublicTrustCenterDistributionKitAcceptanceError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except PublicTrustCenterAcceptanceBoardNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PublicTrustCenterAcceptanceBoardStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PublicTrustCenterAcceptanceBoardError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
