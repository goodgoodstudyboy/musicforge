from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class ProgramUccEvidence_DetailRoutes:
    def _dispatch_ucc_evidence_detail(self, method, center_id, tail) -> bool:
        if tail.startswith('/evidence-reviews/'):
            review_tail = tail.removeprefix('/evidence-reviews/')
            review_parts = review_tail.split('/')
            review_id = review_parts[0]
            review_action = '/' + '/'.join(review_parts[1:]) if len(review_parts) > 1 else ''
            if review_action in {'', '/'}:
                if method != 'GET':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                review = self.unified_command_center_evidence_review_store.get_review(center_id, review_id)
                replay = review.get('replay_result') or {}
                self._send_json({'ok': True, 'review': review, 'summary': replay.get('summary', {}), 'status': replay.get('status') or (review.get('source') or {}).get('status')})
                return True
            if review_action == '/refresh':
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                docs = self.unified_command_center_evidence_review_store.refresh_review(center_id, review_id, self._optional_json_body())
                source = docs.get('source', {})
                self._send_json({'ok': True, 'review': docs, 'summary': {'review_id': review_id}, 'status': source.get('status')})
                return True
            if review_action == '/replay':
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                replay = self.unified_command_center_evidence_review_store.run_replay(center_id, review_id, self._optional_json_body())
                self._send_json({'ok': replay.get('status') == 'passed', 'replay_result': replay, 'summary': replay.get('summary', {}), 'status': replay.get('status')})
                return True
            if review_action == '/export':
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                result = self.unified_command_center_evidence_review_store.export_review(center_id, review_id, self._optional_json_body())
                self._send_json({'ok': result.get('status') == 'passed', **result})
                return True
            if review_action == '/zip':
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                result = self.unified_command_center_evidence_review_store.build_zip(center_id, review_id, self._optional_json_body())
                self._send_json({'ok': result.get('status') == 'passed', **result, 'summary': {'zip_sha256': result.get('zip_sha256')}})
                return True
            if review_action == '/verify':
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                report = self.unified_command_center_evidence_review_store.verify_zip(center_id, review_id, self._optional_json_body())
                self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
                return True
            if review_action == '/download':
                if method != 'GET':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                self._send_file(self.unified_command_center_evidence_review_store.zip_path(center_id, review_id), 'application/zip', filename='musicforge-unified-command-center-evidence-review.zip')
                return True
            if review_action == '/responses':
                if method != 'GET':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                responses = self.unified_command_center_evidence_review_store.list_responses(center_id, review_id)
                self._send_json({'ok': True, 'responses': responses, 'summary': {'response_count': len(responses)}})
                return True
            if review_action == '/responses/import':
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                response = self.unified_command_center_evidence_review_store.import_response(center_id, review_id, self._read_json_body())
                self._send_json({'ok': response.get('status') == 'current', 'response': response, 'summary': {'response_id': response.get('response_id')}, 'status': response.get('status')}, status=HTTPStatus.CREATED)
                return True
            if review_action.startswith('/responses/') and review_action.endswith('/accepted-evidence'):
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                response_id = review_action.split('/')[2]
                result = self.unified_command_center_evidence_review_store.create_acceptance_evidence(center_id, review_id, response_id)
                self._send_json({'ok': result.get('status') == 'passed', **result, 'summary': {'evidence_id': result.get('evidence_id')}}, status=HTTPStatus.CREATED)
                return True
            if review_action.startswith('/accepted-evidence/'):
                evidence_tail = review_action.removeprefix('/accepted-evidence/')
                evidence_parts = evidence_tail.split('/')
                evidence_id = evidence_parts[0]
                evidence_action = '/' + '/'.join(evidence_parts[1:]) if len(evidence_parts) > 1 else ''
                if evidence_action == '/verify':
                    if method != 'POST':
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                        return True
                    report = self.unified_command_center_evidence_review_store.verify_acceptance_evidence(center_id, review_id, evidence_id, self._optional_json_body())
                    self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
                    return True
                if evidence_action == '/download':
                    if method != 'GET':
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                        return True
                    self._send_file(self.unified_command_center_evidence_review_store.accepted_evidence_zip_path(center_id, review_id, evidence_id), 'application/zip', filename='musicforge-unified-command-center-evidence-review-acceptance.zip')
                    return True
            self._send_error(HTTPStatus.NOT_FOUND, 'Unified Command Center Evidence Review route not found.')
            return True
        return False
