from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class TrustRoutesPublicTrustCenters:
    def _handle_public_trust_centers_part_01(self, method: str, path: str, _split_state):
        if _split_state['tail'] in {'', '/'}:
            if method == 'GET':
                centers = self.public_trust_center_store.list_centers()
                self._send_json({'ok': True, 'centers': centers, 'summary': {'count': len(centers)}})
                return (True, None)
            if method == 'POST':
                config = self.public_trust_center_store.create_or_update_center(self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'center': config, 'summary': _interfaces_api_runtime.public_trust_center_summary(self.public_trust_center_store.read_report(str(config.get('center_id') or 'ptc-default'), default={}))}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        _split_state['parts'] = [part for part in _split_state['tail'].strip('/').split('/') if part]
        if not _split_state['parts']:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Public Trust Center route not found.')
            return (True, None)
        _split_state['center_id'] = _split_state['parts'][0]
        if _split_state['center_id'].endswith('.zip') and len(_split_state['parts']) == 1:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            actual_id = _split_state['center_id'][:-4]
            self.public_trust_center_store.get_center(actual_id)
            self._send_file(self.public_trust_center_store.zip_path(actual_id), 'application/zip', filename=f'musicforge-{actual_id}-public-trust-center.zip')
            return (True, None)
        _split_state['action'] = _split_state['parts'][1] if len(_split_state['parts']) > 1 else ''
        if len(_split_state['parts']) == 1:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            detail = self.public_trust_center_store.get_center(_split_state['center_id'])
            self._send_json({'ok': True, **detail})
            return (True, None)
        if _split_state['action'] == 'refresh' and len(_split_state['parts']) == 2:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['report'] = self.public_trust_center_store.refresh_report(_split_state['center_id'], self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'report': _split_state['report'], 'summary': _interfaces_api_runtime.public_trust_center_summary(_split_state['report'])}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if _split_state['action'] == 'export' and len(_split_state['parts']) == 2:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['manifest'] = self.public_trust_center_store.export_center(_split_state['center_id'], self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'manifest': _split_state['manifest'], 'summary': {'source_hash': _split_state['manifest'].get('source_hash'), 'package_type': _split_state['manifest'].get('package_type')}}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if _split_state['action'] == 'zip' and len(_split_state['parts']) == 2:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['zip_info'] = self.public_trust_center_store.build_zip(_split_state['center_id'], self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'zip': _split_state['zip_info']})
            return (True, None)
        return (False, None)

    def _handle_public_trust_centers_part_02(self, method: str, path: str, _split_state):
        if _split_state['action'] == 'verify' and len(_split_state['parts']) == 2:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            _split_state['report'] = _interfaces_api_runtime.verify_public_trust_center_package(self.public_trust_center_store.zip_path(_split_state['center_id']), strict=bool(_split_state['payload'].get('strict', True)), require_registry_current=bool(_split_state['payload'].get('require_registry_current', False)), require_portal_current=bool(_split_state['payload'].get('require_portal_current', False)), require_transparency_current=bool(_split_state['payload'].get('require_transparency_current', False)), require_acknowledgement_current=bool(_split_state['payload'].get('require_acknowledgement_current', False)), require_release_readiness=bool(_split_state['payload'].get('require_release_readiness', False)), require_delivery_readiness=bool(_split_state['payload'].get('require_delivery_readiness', False)), require_distribution_ready=bool(_split_state['payload'].get('require_distribution_ready', False)), require_submission_accepted=bool(_split_state['payload'].get('require_submission_accepted', False)), require_submission_evidence=bool(_split_state['payload'].get('require_submission_evidence', False)), require_operations_signed=bool(_split_state['payload'].get('require_operations_signed', False)), require_operations_audit=bool(_split_state['payload'].get('require_operations_audit', False)), require_operations_reviewer_pack=bool(_split_state['payload'].get('require_operations_reviewer_pack', False)), delivery_anchor_path=self.public_trust_center_store.delivery_anchor_path(_split_state['center_id']), anchor_registry_path=self.public_trust_center_anchor_registry_store.zip_path(_split_state['center_id']) if bool(_split_state['payload'].get('require_anchor_registry_current', False)) or bool(_split_state['payload'].get('require_anchor_published', False)) or bool(_split_state['payload'].get('require_anchor_not_revoked', False)) or bool(_split_state['payload'].get('use_anchor_registry', False)) else None, anchor_transparency_path=self.public_trust_center_anchor_transparency_store.zip_path(_split_state['center_id']) if bool(_split_state['payload'].get('require_anchor_transparency_current', False)) or bool(_split_state['payload'].get('require_anchor_checkpoint', False)) or bool(_split_state['payload'].get('use_anchor_transparency', False)) else None, anchor_checkpoint_path=self.public_trust_center_anchor_transparency_store.current_checkpoint_path(_split_state['center_id']) if bool(_split_state['payload'].get('require_anchor_checkpoint', False)) or bool(_split_state['payload'].get('use_anchor_transparency', False)) else None, require_anchor_registry_current=bool(_split_state['payload'].get('require_anchor_registry_current', False)), require_anchor_published=bool(_split_state['payload'].get('require_anchor_published', False)), require_anchor_not_revoked=bool(_split_state['payload'].get('require_anchor_not_revoked', False)), require_anchor_transparency_current=bool(_split_state['payload'].get('require_anchor_transparency_current', False)), require_anchor_checkpoint=bool(_split_state['payload'].get('require_anchor_checkpoint', False)))
            _interfaces_api_runtime.write_public_trust_center_verification_report(_split_state['report'], self.public_trust_center_store.verification_report_path(_split_state['center_id']))
            self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'verification': _split_state['report'], 'summary': _split_state['report'].get('summary', {})})
            return (True, None)
        return (False, None)

    def _handle_public_trust_centers_part_03(self, method: str, path: str, _split_state):
        if _split_state['action'] == 'anchor-registry':
            if len(_split_state['parts']) == 2:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                registry = self.public_trust_center_anchor_registry_store.read_registry(_split_state['center_id'], default={})
                _split_state['report'] = self.public_trust_center_anchor_registry_store.read_report(_split_state['center_id'], default={})
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'registry': registry, 'report': _split_state['report'], 'summary': self.public_trust_center_anchor_registry_store.summary(_split_state['center_id'])})
                return (True, None)
            _split_state['subaction'] = _split_state['parts'][2] if len(_split_state['parts']) > 2 else ''
            if _split_state['subaction'] == 'download' and len(_split_state['parts']) == 3:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                self._send_file(self.public_trust_center_anchor_registry_store.zip_path(_split_state['center_id']), 'application/zip', filename=f"musicforge-{_split_state['center_id']}-anchor-registry.zip")
                return (True, None)
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            if _split_state['subaction'] == 'register-current' and len(_split_state['parts']) == 3:
                result = self.public_trust_center_anchor_registry_store.register_current_anchor(_split_state['center_id'], _split_state['payload'], now=_interfaces_api_runtime._utc_now())
                status = _interfaces_api_runtime.HTTPStatus.OK if result.get('existing') else _interfaces_api_runtime.HTTPStatus.CREATED
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], **result, 'summary': _interfaces_api_runtime.public_trust_center_anchor_registry_summary(result.get('registry') if isinstance(result.get('registry'), dict) else {})}, status=status)
                return (True, None)
            if _split_state['subaction'] == 'publish' and len(_split_state['parts']) == 4:
                result = self.public_trust_center_anchor_registry_store.publish_entry(_split_state['center_id'], _split_state['parts'][3], _split_state['payload'], now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], **result, 'summary': _interfaces_api_runtime.public_trust_center_anchor_registry_summary(result.get('registry') if isinstance(result.get('registry'), dict) else {})})
                return (True, None)
            if _split_state['subaction'] == 'revoke' and len(_split_state['parts']) == 4:
                result = self.public_trust_center_anchor_registry_store.revoke_entry(_split_state['center_id'], _split_state['parts'][3], _split_state['payload'], now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], **result, 'summary': _interfaces_api_runtime.public_trust_center_anchor_registry_summary(result.get('registry') if isinstance(result.get('registry'), dict) else {})})
                return (True, None)
            if _split_state['subaction'] == 'supersede' and len(_split_state['parts']) == 4:
                result = self.public_trust_center_anchor_registry_store.supersede_entry(_split_state['center_id'], _split_state['parts'][3], _split_state['payload'], now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], **result, 'summary': _interfaces_api_runtime.public_trust_center_anchor_registry_summary(result.get('registry') if isinstance(result.get('registry'), dict) else {})})
                return (True, None)
            if _split_state['subaction'] == 'refresh' and len(_split_state['parts']) == 3:
                _split_state['report'] = self.public_trust_center_anchor_registry_store.refresh_report(_split_state['center_id'], _split_state['payload'], now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'report': _split_state['report'], 'summary': _interfaces_api_runtime.public_trust_center_anchor_registry_summary(self.public_trust_center_anchor_registry_store.read_registry(_split_state['center_id'], default={}))}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            if _split_state['subaction'] == 'export' and len(_split_state['parts']) == 3:
                _split_state['manifest'] = self.public_trust_center_anchor_registry_store.export_registry(_split_state['center_id'], _split_state['payload'], now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'manifest': _split_state['manifest'], 'summary': {'source_hash': _split_state['manifest'].get('source_hash'), 'package_type': _split_state['manifest'].get('package_type')}}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            if _split_state['subaction'] == 'zip' and len(_split_state['parts']) == 3:
                _split_state['zip_info'] = self.public_trust_center_anchor_registry_store.build_zip(_split_state['center_id'], _split_state['payload'], now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'zip': _split_state['zip_info']})
                return (True, None)
            if _split_state['subaction'] == 'verify' and len(_split_state['parts']) == 3:
                _split_state['report'] = _interfaces_api_runtime.verify_public_trust_center_anchor_registry_package(self.public_trust_center_anchor_registry_store.zip_path(_split_state['center_id']), strict=bool(_split_state['payload'].get('strict', True)), require_current=bool(_split_state['payload'].get('require_current', False)), require_anchor_published=bool(_split_state['payload'].get('require_anchor_published', False)), require_anchor_not_revoked=bool(_split_state['payload'].get('require_anchor_not_revoked', False)))
                _interfaces_api_runtime.write_public_trust_center_anchor_registry_verification_report(_split_state['report'], self.public_trust_center_anchor_registry_store.verification_report_path(_split_state['center_id']))
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'verification': _split_state['report'], 'summary': _split_state['report'].get('summary', {})})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Public Trust Center Anchor Registry route not found.')
            return (True, None)
        return (False, None)

    def _handle_public_trust_centers_part_04(self, method: str, path: str, _split_state):
        if _split_state['action'] == 'anchor-transparency':
            if len(_split_state['parts']) == 2:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['report'] = self.public_trust_center_anchor_transparency_store.read_report(_split_state['center_id'], default={})
                checkpoint = self.public_trust_center_anchor_transparency_store.read_checkpoint(_split_state['center_id'], default={})
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'report': _split_state['report'], 'checkpoint': checkpoint, 'summary': self.public_trust_center_anchor_transparency_store.summary(_split_state['center_id'])})
                return (True, None)
            _split_state['subaction'] = _split_state['parts'][2] if len(_split_state['parts']) > 2 else ''
            if _split_state['subaction'] == 'download' and len(_split_state['parts']) == 3:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                self._send_file(self.public_trust_center_anchor_transparency_store.zip_path(_split_state['center_id']), 'application/zip', filename=f"musicforge-{_split_state['center_id']}-anchor-transparency.zip")
                return (True, None)
            if _split_state['subaction'] == 'checkpoint' and len(_split_state['parts']) == 3:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                self._send_file(self.public_trust_center_anchor_transparency_store.current_checkpoint_path(_split_state['center_id']), 'application/json', filename=f"musicforge-{_split_state['center_id']}-anchor-checkpoint.json")
                return (True, None)
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            if _split_state['subaction'] == 'refresh' and len(_split_state['parts']) == 3:
                _split_state['report'] = self.public_trust_center_anchor_transparency_store.refresh_report(_split_state['center_id'], _split_state['payload'], now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'report': _split_state['report'], 'summary': _interfaces_api_runtime.public_trust_center_anchor_transparency_summary(_split_state['report'])}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            if _split_state['subaction'] == 'checkpoint' and len(_split_state['parts']) == 4 and (_split_state['parts'][3] == 'create'):
                checkpoint = self.public_trust_center_anchor_transparency_store.create_checkpoint(_split_state['center_id'], _split_state['payload'], now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'checkpoint': checkpoint}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            if _split_state['subaction'] == 'export' and len(_split_state['parts']) == 3:
                _split_state['manifest'] = self.public_trust_center_anchor_transparency_store.export_transparency(_split_state['center_id'], _split_state['payload'], now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'manifest': _split_state['manifest'], 'summary': {'source_hash': _split_state['manifest'].get('source_hash'), 'package_type': _split_state['manifest'].get('package_type')}}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            if _split_state['subaction'] == 'zip' and len(_split_state['parts']) == 3:
                _split_state['zip_info'] = self.public_trust_center_anchor_transparency_store.build_zip(_split_state['center_id'], _split_state['payload'], now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'zip': _split_state['zip_info']})
                return (True, None)
            if _split_state['subaction'] == 'verify' and len(_split_state['parts']) == 3:
                _split_state['report'] = _interfaces_api_runtime.verify_public_trust_center_anchor_transparency_package(self.public_trust_center_anchor_transparency_store.zip_path(_split_state['center_id']), strict=bool(_split_state['payload'].get('strict', True)), checkpoint_path=self.public_trust_center_anchor_transparency_store.current_checkpoint_path(_split_state['center_id']) if bool(_split_state['payload'].get('require_current_checkpoint', False)) or bool(_split_state['payload'].get('use_checkpoint', False)) else None, anchor_registry_path=self.public_trust_center_anchor_registry_store.zip_path(_split_state['center_id']) if bool(_split_state['payload'].get('use_anchor_registry', False)) or bool(_split_state['payload'].get('require_published_anchor', False)) or bool(_split_state['payload'].get('require_not_revoked', False)) else None, require_current_checkpoint=bool(_split_state['payload'].get('require_current_checkpoint', False)), require_published_anchor=bool(_split_state['payload'].get('require_published_anchor', False)), require_not_revoked=bool(_split_state['payload'].get('require_not_revoked', False)))
                _interfaces_api_runtime.write_public_trust_center_anchor_transparency_verification_report(_split_state['report'], self.public_trust_center_anchor_transparency_store.verification_report_path(_split_state['center_id']))
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'verification': _split_state['report'], 'summary': _split_state['report'].get('summary', {})})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Public Trust Center Anchor Transparency route not found.')
            return (True, None)
        return (False, None)

    def _handle_public_trust_centers_part_05(self, method: str, path: str, _split_state):
        if _split_state['action'] == 'distribution-kit':
            if len(_split_state['parts']) == 2:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['report'] = self.public_trust_center_distribution_kit_store.read_report(_split_state['center_id'], default={})
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'report': _split_state['report'], 'summary': self.public_trust_center_distribution_kit_store.summary(_split_state['center_id'])})
                return (True, None)
            _split_state['subaction'] = _split_state['parts'][2] if len(_split_state['parts']) > 2 else ''
            if _split_state['subaction'] == 'acceptance':
                self._handle_public_trust_center_distribution_kit_acceptance(method, _split_state['center_id'], _split_state['parts'])
                return (True, None)
            if _split_state['subaction'] == 'download' and len(_split_state['parts']) == 3:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                self._send_file(self.public_trust_center_distribution_kit_store.zip_path(_split_state['center_id']), 'application/zip', filename=f"musicforge-{_split_state['center_id']}-distribution-kit.zip")
                return (True, None)
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            if _split_state['subaction'] == 'refresh' and len(_split_state['parts']) == 3:
                _split_state['report'] = self.public_trust_center_distribution_kit_store.refresh_report(_split_state['center_id'], _split_state['payload'], now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'report': _split_state['report'], 'summary': _interfaces_api_runtime.public_trust_center_distribution_kit_summary(_split_state['report'])}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            if _split_state['subaction'] == 'export' and len(_split_state['parts']) == 3:
                _split_state['manifest'] = self.public_trust_center_distribution_kit_store.export_kit(_split_state['center_id'], _split_state['payload'], now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'manifest': _split_state['manifest'], 'summary': {'source_hash': _split_state['manifest'].get('source_hash'), 'package_type': _split_state['manifest'].get('package_type')}}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            if _split_state['subaction'] == 'zip' and len(_split_state['parts']) == 3:
                _split_state['zip_info'] = self.public_trust_center_distribution_kit_store.build_zip(_split_state['center_id'], _split_state['payload'], now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'zip': _split_state['zip_info']})
                return (True, None)
            if _split_state['subaction'] == 'verify' and len(_split_state['parts']) == 3:
                _split_state['report'] = self.public_trust_center_distribution_kit_store.verify_zip(_split_state['center_id'], {'strict': bool(_split_state['payload'].get('strict', True)), 'deep': bool(_split_state['payload'].get('deep', True)), 'require_current': bool(_split_state['payload'].get('require_current', True)), 'require_delivery_readiness': bool(_split_state['payload'].get('require_delivery_readiness', True)), 'require_anchor_registry_current': bool(_split_state['payload'].get('require_anchor_registry_current', True)), 'require_anchor_published': bool(_split_state['payload'].get('require_anchor_published', True)), 'require_anchor_not_revoked': bool(_split_state['payload'].get('require_anchor_not_revoked', True)), 'require_anchor_transparency_current': bool(_split_state['payload'].get('require_anchor_transparency_current', True)), 'require_anchor_checkpoint': bool(_split_state['payload'].get('require_anchor_checkpoint', True))}, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'verification': _split_state['report'], 'summary': _split_state['report'].get('summary', {})})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Public Trust Center Distribution Kit route not found.')
            return (True, None)
        if _split_state['action'] == 'acceptance-board':
            self._handle_public_trust_center_acceptance_board(method, _split_state['center_id'], _split_state['parts'])
            return (True, None)
        if _split_state['action'] == 'archive' and len(_split_state['parts']) == 2:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            archive = self.public_trust_center_store.archive_snapshot(_split_state['center_id'], self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'center_id': _split_state['center_id'], 'archive': archive, 'summary': {'status': 'archived', 'zip_sha256': archive.get('zip_sha256')}})
            return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Public Trust Center route not found.')
        return (False, None)

    def _handle_public_trust_centers(self, method: str, path: str) -> None:
        _split_state = {}
        prefix = '/api/public-trust-centers'
        _split_state['tail'] = path[len(prefix):]
        try:
            _split_result = self._handle_public_trust_centers_part_01(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_public_trust_centers_part_02(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_public_trust_centers_part_03(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_public_trust_centers_part_04(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_public_trust_centers_part_05(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except _interfaces_api_runtime.PublicTrustCenterNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.PublicTrustCenterStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.PublicTrustCenterError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.PublicTrustCenterAnchorRegistryNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.PublicTrustCenterAnchorRegistryStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.PublicTrustCenterAnchorRegistryError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.PublicTrustCenterAnchorTransparencyNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.PublicTrustCenterAnchorTransparencyStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.PublicTrustCenterAnchorTransparencyError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.PublicTrustCenterDistributionKitNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.PublicTrustCenterDistributionKitStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.PublicTrustCenterDistributionKitError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.PublicTrustCenterDistributionKitAcceptanceNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.PublicTrustCenterDistributionKitAcceptanceStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.PublicTrustCenterDistributionKitAcceptanceError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.PublicTrustCenterAcceptanceBoardNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.PublicTrustCenterAcceptanceBoardStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.PublicTrustCenterAcceptanceBoardError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
