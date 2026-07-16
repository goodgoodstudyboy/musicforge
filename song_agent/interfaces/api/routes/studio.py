from __future__ import annotations


import song_agent.interfaces.api.runtime as _interfaces_api_runtime


from song_agent.interfaces.web.assets import web_script

from .studio_parts.edit_presets import StudioRoutesEditPresets

from .studio_parts.get_or_refresh_sprint_judge_summary import StudioRoutesGetOrRefreshSprintJudgeSummary

from .studio_parts.review_sprint_action_queue import StudioRoutesReviewSprintActionQueue

from .studio_parts.apply_review_task_candidate import StudioRoutesApplyReviewTaskCandidate

from .studio_parts.send_html import StudioRoutesSendHtml

from .studio_dispatch_parts.system import StudioSystemDispatch
from .studio_dispatch_parts.jobs import StudioJobsDispatch
from .studio_dispatch_parts.resources import StudioResourcesDispatch
from .studio_dispatch_parts.acceptance_routes import StudioAcceptance_RoutesDispatch
from .studio_dispatch_parts.acceptance_items import StudioAcceptance_ItemsDispatch
from .studio_dispatch_parts.distribution import StudioDistributionDispatch
from .studio_dispatch_parts.library import StudioLibraryDispatch
from .studio_dispatch_parts.dynamic import StudioDynamicDispatch

class StudioRoutes(StudioRoutesEditPresets, StudioRoutesGetOrRefreshSprintJudgeSummary, StudioRoutesReviewSprintActionQueue, StudioRoutesApplyReviewTaskCandidate, StudioRoutesSendHtml, StudioSystemDispatch, StudioJobsDispatch, StudioResourcesDispatch, StudioAcceptance_RoutesDispatch, StudioAcceptance_ItemsDispatch, StudioDistributionDispatch, StudioLibraryDispatch, StudioDynamicDispatch):
    def _send_javascript(self, source: str) -> None:
        body = source.encode("utf-8")
        self.send_response(_interfaces_api_runtime.HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_request(self, method: str) -> None:
        try:
            parsed = _interfaces_api_runtime.urlparse(self.path)
            path = parsed.path
            if method == 'GET' and path.startswith('/assets/musicforge/'):
                try:
                    self._send_javascript(web_script(path.removeprefix('/assets/musicforge/')))
                except FileNotFoundError:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Studio script module not found.')
                return
            if self._auth_required(path) and (not self._is_authorized()):
                self._send_unauthorized()
                return
            if method == 'GET' and path == '/':
                self._send_html(_interfaces_api_runtime.panel_html())
                return
            if method == 'GET' and path == '/api/info':
                self._send_json(_interfaces_api_runtime.api_info(self.auth_config, authorized=not self.auth_config.enabled or self._is_authorized()))
                return
            if method == 'GET' and path == '/api/template':
                self._send_json(_interfaces_api_runtime.api_template())
                return
            if self.route_registry.dispatch(self, method, path, parsed):
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Route not found.')
        except (OSError, ValueError, _interfaces_api_runtime.json.JSONDecodeError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.ContextPackStaleError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ProviderError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.RendererError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.AcceptanceStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.HumanReviewPackStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.AcceptanceNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.HumanReviewPackNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AcceptanceValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.HumanReviewPackValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
