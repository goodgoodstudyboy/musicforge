from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class ProgramUccReviewsRoutes:
    def _dispatch_ucc_reviews(self, method, center_id, tail) -> bool:
        if tail == '/continuous-reviews':
            if method == 'GET':
                reviews = self.unified_command_center_continuous_review_store.list_reviews(center_id)
                self._send_json({'ok': True, 'reviews': reviews, 'summary': {'review_count': len(reviews)}})
                return True
            if method == 'POST':
                plan = self.unified_command_center_continuous_review_store.create_plan(center_id, self._optional_json_body())
                self._send_json({'ok': True, 'plan': plan, 'summary': {'review_id': plan.get('review_id')}, 'status': plan.get('status')}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return True
        if tail.startswith('/continuous-reviews/'):
            review_tail = tail.removeprefix('/continuous-reviews/')
            review_parts = review_tail.split('/')
            review_id = review_parts[0]
            review_action = '/' + '/'.join(review_parts[1:]) if len(review_parts) > 1 else ''
            if review_action in {'', '/'}:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                review = self.unified_command_center_continuous_review_store.read_review(center_id, review_id)
                self._send_json({'ok': True, 'review': review, 'summary': (review.get('drift_report') or {}).get('summary', {}), 'status': (review.get('drift_report') or review.get('plan') or {}).get('status')})
                return True
            if review_action == '/run':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                result = self.unified_command_center_continuous_review_store.run_review(center_id, review_id, self._optional_json_body())
                self._send_json({'ok': result.get('status') == 'passed', **result})
                return True
            if review_action == '/export':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                result = self.unified_command_center_continuous_review_store.export_package(center_id, review_id, self._optional_json_body())
                self._send_json({'ok': result.get('status') == 'passed', **result})
                return True
            if review_action == '/zip':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                result = self.unified_command_center_continuous_review_store.build_zip(center_id, review_id, self._optional_json_body())
                self._send_json({'ok': result.get('status') == 'passed', **result, 'summary': {'zip_sha256': result.get('zip_sha256')}})
                return True
            if review_action == '/verify':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                report = self.unified_command_center_continuous_review_store.verify_package(center_id, review_id, payload)
                self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
                return True
            if review_action == '/download':
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                self._send_file(self.unified_command_center_continuous_review_store.zip_path(center_id, review_id), 'application/zip', filename='musicforge-unified-command-center-continuous-review.zip')
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Unified Command Center Continuous Review route not found.')
            return True
        return False
