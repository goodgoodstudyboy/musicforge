from __future__ import annotations


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class TrustRoutesTrustOperationsKnowledge:
    def _handle_trust_operations_knowledge_part_01(self, method: str, hub_id: str, tail: str, _split_state):
        if tail in {'', '/'}:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            base = {}
            try:
                base = self.trust_operations_incident_knowledge_store.read_base(hub_id)
            except _interfaces_api_runtime.TrustOperationsKnowledgeNotFoundError:
                pass
            self._send_json({'ok': True, 'hub_id': hub_id, 'knowledge_base': base, 'entries': self.trust_operations_incident_knowledge_store.list_entries(hub_id), 'guards': self.trust_operations_incident_knowledge_store.list_guards(hub_id)})
            return (True, None)
        if tail == '/refresh':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            result = self.trust_operations_incident_knowledge_store.refresh(hub_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, **result}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if tail == '/recurrence/refresh':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            report = self.trust_operations_incident_knowledge_store.refresh_recurrence(hub_id, now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': report.get('status') == 'passed', 'hub_id': hub_id, 'recurrence': report})
            return (True, None)
        if tail == '/guards/run-all':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            result = self.trust_operations_incident_knowledge_store.run_all_guards(hub_id, now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, **result})
            return (True, None)
        if tail == '/export':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            manifest = self.trust_operations_incident_knowledge_store.export_knowledge(hub_id, now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'hub_id': hub_id, 'manifest': manifest}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if tail == '/zip':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            zip_info = self.trust_operations_incident_knowledge_store.build_zip(hub_id, now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'hub_id': hub_id, 'zip': zip_info})
            return (True, None)
        if tail == '/verify':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            report = self.trust_operations_incident_knowledge_store.verify_zip(hub_id, self._optional_json_body())
            _interfaces_api_runtime.write_trust_operations_incident_knowledge_verification_report(report, self.trust_operations_incident_knowledge_store.verification_report_path(hub_id))
            self._send_json({'ok': report.get('status') != 'failed', 'hub_id': hub_id, 'verification': report, 'summary': report.get('summary', {})})
            return (True, None)
        _split_state['parts'] = [part for part in tail.split('/') if part]
        return (False, None)

    def _handle_trust_operations_knowledge_part_02(self, method: str, hub_id: str, tail: str, _split_state):
        if len(_split_state['parts']) >= 2 and _split_state['parts'][0] == 'entries':
            entry_id = _interfaces_api_runtime.unquote(_split_state['parts'][1])
            if len(_split_state['parts']) == 2:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                entry = self.trust_operations_incident_knowledge_store.read_entry(hub_id, entry_id)
                self._send_json({'ok': True, 'hub_id': hub_id, 'entry': entry})
                return (True, None)
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            payload = self._optional_json_body()
            action = _split_state['parts'][2]
            if action == 'hide':
                entry = self.trust_operations_incident_knowledge_store.hide_entry(hub_id, entry_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'hub_id': hub_id, 'entry': entry})
                return (True, None)
            if action == 'unhide':
                entry = self.trust_operations_incident_knowledge_store.unhide_entry(hub_id, entry_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'hub_id': hub_id, 'entry': entry})
                return (True, None)
            if action == 'guards':
                guard = self.trust_operations_incident_knowledge_store.create_guard(hub_id, entry_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'hub_id': hub_id, 'guard': guard}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
        if len(_split_state['parts']) >= 2 and _split_state['parts'][0] == 'guards':
            guard_id = _interfaces_api_runtime.unquote(_split_state['parts'][1])
            if len(_split_state['parts']) == 2:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                guard = self.trust_operations_incident_knowledge_store.read_guard(hub_id, guard_id)
                self._send_json({'ok': True, 'hub_id': hub_id, 'guard': guard})
                return (True, None)
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            if _split_state['parts'][2] == 'run':
                run = self.trust_operations_incident_knowledge_store.run_guard(hub_id, guard_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': run.get('status') == 'passed', 'hub_id': hub_id, 'guard_run': run})
                return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Trust Operations Knowledge route not found.')
        return (False, None)

    def _handle_trust_operations_knowledge(self, method: str, hub_id: str, tail: str) -> None:
        _split_state = {}
        try:
            _split_result = self._handle_trust_operations_knowledge_part_01(method, hub_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_trust_operations_knowledge_part_02(method, hub_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except _interfaces_api_runtime.TrustOperationsKnowledgeNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.TrustOperationsKnowledgeStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (ValueError, _interfaces_api_runtime.json.JSONDecodeError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))

    def _handle_trust_operations_control_signoff_part_01(self, method: str, hub_id: str, tail: str, _split_state):
        if tail in {'', '/'}:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._send_json({'ok': True, **self.trust_operations_control_signoff_store.summary(hub_id)})
            return (True, None)
        if tail == '/download':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._send_file(self.trust_operations_control_signoff_store.archive_zip_path(hub_id), 'application/zip', filename=f'musicforge-{hub_id}-trust-operations-control-signoff.zip')
            return (True, None)
        if tail == '/sign':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            payload = self._optional_json_body()
            assessment_id = str(payload.get('assessment_id') or '')
            if not assessment_id:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, 'assessment_id is required.')
                return (True, None)
            signoff = self.trust_operations_control_signoff_store.sign(hub_id, assessment_id, payload, now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'hub_id': hub_id, 'signoff': signoff}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if tail == '/exceptions':
            if method == 'GET':
                self._send_json({'ok': True, 'hub_id': hub_id, 'exceptions': self.trust_operations_control_signoff_store.list_exceptions(hub_id)})
                return (True, None)
            if method == 'POST':
                _split_state['exception'] = self.trust_operations_control_signoff_store.request_exception(hub_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'hub_id': hub_id, 'exception': _split_state['exception']}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if tail == '/change-requests':
            if method == 'GET':
                self._send_json({'ok': True, 'hub_id': hub_id, 'change_requests': self.trust_operations_control_signoff_store.list_change_requests(hub_id)})
                return (True, None)
            if method == 'POST':
                _split_state['cr'] = self.trust_operations_control_signoff_store.create_change_request(hub_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'hub_id': hub_id, 'change_request': _split_state['cr']}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if tail == '/reset':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            payload = self._optional_json_body()
            cr_id = str(payload.get('change_request_id') or '')
            if not cr_id:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, 'change_request_id is required.')
                return (True, None)
            result = self.trust_operations_control_signoff_store.reset_signoff(hub_id, cr_id, now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'hub_id': hub_id, **result})
            return (True, None)
        if tail == '/export':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            manifest = self.trust_operations_control_signoff_store.export_archive(hub_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'hub_id': hub_id, 'manifest': manifest}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if tail == '/zip':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            zip_info = self.trust_operations_control_signoff_store.build_archive_zip(hub_id, now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'hub_id': hub_id, 'zip': zip_info})
            return (True, None)
        return (False, None)

    def _handle_trust_operations_control_signoff_part_02(self, method: str, hub_id: str, tail: str, _split_state):
        if tail == '/verify':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            report = self.trust_operations_control_signoff_store.verify_archive_zip(hub_id, self._optional_json_body())
            _interfaces_api_runtime.write_trust_operations_control_signoff_verification_report(report, self.trust_operations_control_signoff_store.verification_report_path(hub_id))
            self._send_json({'ok': report.get('status') != 'failed', 'hub_id': hub_id, 'verification': report, 'summary': report.get('summary', {})})
            return (True, None)
        parts = [part for part in tail.split('/') if part]
        if len(parts) == 3 and parts[0] == 'exceptions' and (parts[2] in {'approve', 'reject'}):
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            if parts[2] == 'approve':
                _split_state['exception'] = self.trust_operations_control_signoff_store.approve_exception(hub_id, _interfaces_api_runtime.unquote(parts[1]), self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            else:
                _split_state['exception'] = self.trust_operations_control_signoff_store.reject_exception(hub_id, _interfaces_api_runtime.unquote(parts[1]), self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'hub_id': hub_id, 'exception': _split_state['exception']})
            return (True, None)
        if len(parts) == 3 and parts[0] == 'change-requests' and (parts[2] == 'approve'):
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['cr'] = self.trust_operations_control_signoff_store.approve_change_request(hub_id, _interfaces_api_runtime.unquote(parts[1]), self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'hub_id': hub_id, 'change_request': _split_state['cr']})
            return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Trust Operations Control Signoff route not found.')
        return (False, None)

    def _handle_trust_operations_control_signoff(self, method: str, hub_id: str, tail: str) -> None:
        _split_state = {}
        try:
            _split_result = self._handle_trust_operations_control_signoff_part_01(method, hub_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_trust_operations_control_signoff_part_02(method, hub_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except _interfaces_api_runtime.TrustOperationsControlSignoffNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.TrustOperationsControlSignoffStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (ValueError, _interfaces_api_runtime.json.JSONDecodeError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))

    def _handle_trust_operations_controls(self, method: str, hub_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                catalog = {}
                try:
                    catalog = self.trust_operations_control_store.read_catalog(hub_id)
                except _interfaces_api_runtime.TrustOperationsControlNotFoundError:
                    pass
                self._send_json({"ok": True, "hub_id": hub_id, "catalog": catalog, "policies": self.trust_operations_control_store.list_policies(hub_id)})
                return
            if tail == "/catalog/refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                catalog = self.trust_operations_control_store.refresh_catalog(hub_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "hub_id": hub_id, "catalog": catalog}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if tail == "/policies":
                if method == "GET":
                    self._send_json({"ok": True, "hub_id": hub_id, "policies": self.trust_operations_control_store.list_policies(hub_id)})
                    return
                if method == "POST":
                    policy = self.trust_operations_control_store.create_policy_bundle(hub_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "hub_id": hub_id, "policy": policy}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail == "/assess":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                policy_id = str(payload.get("policy_id") or "")
                if not policy_id:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, "policy_id is required.")
                    return
                result = self.trust_operations_control_store.assess_policy(hub_id, policy_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": result.get("assessment", {}).get("status") == "passed", "hub_id": hub_id, **result}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            parts = [part for part in tail.split("/") if part]
            if len(parts) == 2 and parts[0] == "policies":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                policy = self.trust_operations_control_store.read_policy(hub_id, _interfaces_api_runtime.unquote(parts[1]))
                self._send_json({"ok": True, "hub_id": hub_id, "policy": policy})
                return
            if len(parts) >= 2 and parts[0] == "assessments":
                assessment_id = _interfaces_api_runtime.unquote(parts[1])
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    assessment = self.trust_operations_control_store.read_assessment(hub_id, assessment_id)
                    self._send_json({"ok": True, "hub_id": hub_id, "assessment": assessment})
                    return
                action = parts[2]
                if action == "export":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    manifest = self.trust_operations_control_store.export_controls(hub_id, assessment_id, now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "hub_id": hub_id, "manifest": manifest}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                if action == "zip":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    zip_info = self.trust_operations_control_store.build_zip(hub_id, assessment_id, now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "hub_id": hub_id, "zip": zip_info})
                    return
                if action == "verify":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.trust_operations_control_store.verify_zip(hub_id, assessment_id, self._optional_json_body())
                    _interfaces_api_runtime.write_trust_operations_control_verification_report(report, self.trust_operations_control_store.verification_report_path(hub_id, assessment_id))
                    self._send_json({"ok": report.get("status") != "failed", "hub_id": hub_id, "verification": report, "summary": report.get("summary", {})})
                    return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Trust Operations Control route not found.")
        except _interfaces_api_runtime.TrustOperationsControlNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.TrustOperationsControlStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (ValueError, _interfaces_api_runtime.json.JSONDecodeError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
