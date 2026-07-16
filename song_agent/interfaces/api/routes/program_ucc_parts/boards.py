from __future__ import annotations


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class ProgramUccBoardsRoutes:
    def _dispatch_ucc_boards(self, method, center_id, tail) -> bool:
        if tail == '/reviewer-decision-boards':
            if method == 'GET':
                boards = self.unified_command_center_reviewer_decision_board_store.list_boards(center_id)
                self._send_json({'ok': True, 'boards': boards, 'summary': {'board_count': len(boards)}})
                return True
            if method == 'POST':
                docs = self.unified_command_center_reviewer_decision_board_store.create_board(center_id, self._optional_json_body())
                decision = docs.get('decision_report', {})
                self._send_json({'ok': decision.get('status') == 'ready_for_signoff', 'board': docs, 'summary': decision.get('summary', {}), 'status': decision.get('status')}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return True
        if tail.startswith('/reviewer-decision-boards/'):
            board_tail = tail.removeprefix('/reviewer-decision-boards/')
            board_parts = board_tail.split('/')
            board_id = board_parts[0]
            board_action = '/' + '/'.join(board_parts[1:]) if len(board_parts) > 1 else ''
            if board_action in {'', '/'}:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                board = self.unified_command_center_reviewer_decision_board_store.get_board(center_id, board_id)
                decision = board.get('decision_report') or {}
                self._send_json({'ok': True, 'board': board, 'summary': decision.get('summary', {}), 'status': decision.get('status')})
                return True
            if board_action == '/refresh':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                docs = self.unified_command_center_reviewer_decision_board_store.refresh_board(center_id, board_id, self._optional_json_body())
                decision = docs.get('decision_report', {})
                self._send_json({'ok': decision.get('status') == 'ready_for_signoff', 'board': docs, 'summary': decision.get('summary', {}), 'status': decision.get('status')})
                return True
            if board_action == '/signoff':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                signoff = self.unified_command_center_reviewer_decision_board_store.signoff(center_id, board_id, self._optional_json_body())
                self._send_json({'ok': signoff.get('status') == 'signed', 'signoff': signoff, 'summary': {'signoff_hash': signoff.get('integrity_hash')}, 'status': signoff.get('status')})
                return True
            if board_action == '/export':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                result = self.unified_command_center_reviewer_decision_board_store.export_archive(center_id, board_id, self._optional_json_body())
                self._send_json({'ok': result.get('status') == 'signed', **result})
                return True
            if board_action == '/zip':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                result = self.unified_command_center_reviewer_decision_board_store.build_zip(center_id, board_id, self._optional_json_body())
                self._send_json({'ok': result.get('status') == 'passed', **result, 'summary': {'zip_sha256': result.get('zip_sha256')}})
                return True
            if board_action == '/verify':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                report = self.unified_command_center_reviewer_decision_board_store.verify_archive(center_id, board_id, self._optional_json_body())
                self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
                return True
            if board_action == '/download':
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                self._send_file(self.unified_command_center_reviewer_decision_board_store.zip_path(center_id, board_id), 'application/zip', filename='musicforge-unified-command-center-reviewer-decision-board.zip')
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Unified Command Center Reviewer Decision Board route not found.')
            return True
        return False
