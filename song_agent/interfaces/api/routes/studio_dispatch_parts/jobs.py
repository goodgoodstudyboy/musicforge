from __future__ import annotations

from song_agent.interfaces.api.route_contexts.studio_dispatch import StudioDispatchRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class StudioJobsDispatch(StudioDispatchRouteContext):
    def _dispatch_studio_jobs(self, method, path, parsed) -> bool:
        if path == '/api/jobs':
            if method == 'GET':
                query = _interfaces_api_runtime.parse_qs(parsed.query)
                include_hidden = query.get('include_hidden', ['0'])[0] in {'1', 'true', 'yes'}
                self._send_json({'jobs': [job.to_dict() for job in self.store.list_jobs(include_hidden=include_hidden)]})
                return True
            if method == 'POST':
                payload = self._read_json_body()
                payload = self._expand_context_pack_payload(payload)
                job = self.store.create_job(payload)
                self._send_json(job.to_dict(), status=_interfaces_api_runtime.HTTPStatus.ACCEPTED)
                return True
        if path == '/api/batches':
            if method == 'GET':
                query = _interfaces_api_runtime.parse_qs(parsed.query)
                include_hidden = query.get('include_hidden', ['0'])[0] in {'1', 'true', 'yes'}
                self._send_json({'batches': [document.state.to_dict() for document in self.batch_store.list_batches(include_hidden=include_hidden)]})
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return True
        if path == '/api/batches/import-csv':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._read_json_body()
            document = self.batch_store.import_csv(name=str(payload.get('name') or 'Untitled Batch'), csv_text=str(payload.get('csv_text') or ''), generation_mode=str(payload.get('generation_mode') or 'local'), pipeline_mode=str(payload.get('pipeline_mode') or 'multinode'), max_concurrency=payload.get('max_concurrency', 1))
            self._send_json(document.to_dict(), status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return True
        if path == '/api/projects':
            self._handle_projects_root(method, parsed.query)
            return True
        return False
