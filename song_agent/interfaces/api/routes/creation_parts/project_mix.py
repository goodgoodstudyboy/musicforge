from __future__ import annotations

from song_agent.interfaces.api.route_contexts.creation import CreationRouteContext
from song_agent.interfaces.bootstrap.api import creation_quality as _api_store_factories

from .project_editor_auditions import CreationProjectEditorAuditionRoutes
from .project_mix_operations import CreationProjectMixOperations

import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class CreationRoutesProjectMix(CreationProjectMixOperations, CreationProjectEditorAuditionRoutes, CreationRouteContext):
    def _handle_project_mix_route(self, method: str, project_id: str, version_id: str, action: str, resource_id: str | None = None) -> None:
        mix_store = _api_store_factories.mix_render_store(self.project_store, self.store)
        control_store = _api_store_factories.mix_control_store(self.project_store.project_dir(project_id))
        try:
            if self._handle_project_mix_route_part_01(method, project_id, version_id, action, resource_id, mix_store, control_store):
                return
            if self._handle_project_mix_route_part_02(method, project_id, version_id, action, resource_id, mix_store):
                return
        except StopIteration:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except FileNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc) or "Mix resource not found.")
            return
        except _interfaces_api_runtime.MixControlStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
            return
        except (_interfaces_api_runtime.MixControlError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Mix route not found.")
