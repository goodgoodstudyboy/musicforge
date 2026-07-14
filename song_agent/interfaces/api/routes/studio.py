from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

from song_agent.interfaces.api.routes.program_registry import PROGRAM_ROUTE_REGISTRY

from song_agent.interfaces.web.assets import web_script

from .studio_parts.part_001 import StudioRoutesPart001

from .studio_parts.part_002 import StudioRoutesPart002

from .studio_parts.part_003 import StudioRoutesPart003

from .studio_parts.part_004 import StudioRoutesPart004

from .studio_parts.part_005 import StudioRoutesPart005

from .studio_dispatch_parts.system import StudioSystemDispatch
from .studio_dispatch_parts.jobs import StudioJobsDispatch
from .studio_dispatch_parts.resources import StudioResourcesDispatch
from .studio_dispatch_parts.acceptance_routes import StudioAcceptance_RoutesDispatch
from .studio_dispatch_parts.acceptance_items import StudioAcceptance_ItemsDispatch
from .studio_dispatch_parts.distribution import StudioDistributionDispatch
from .studio_dispatch_parts.library import StudioLibraryDispatch
from .studio_dispatch_parts.dynamic import StudioDynamicDispatch

class StudioRoutes(StudioRoutesPart001, StudioRoutesPart002, StudioRoutesPart003, StudioRoutesPart004, StudioRoutesPart005, StudioSystemDispatch, StudioJobsDispatch, StudioResourcesDispatch, StudioAcceptance_RoutesDispatch, StudioAcceptance_ItemsDispatch, StudioDistributionDispatch, StudioLibraryDispatch, StudioDynamicDispatch):
    def _send_javascript(self, source: str) -> None:
        body = source.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_request(self, method: str) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if method == 'GET' and path.startswith('/assets/musicforge/'):
                try:
                    self._send_javascript(web_script(path.removeprefix('/assets/musicforge/')))
                except FileNotFoundError:
                    self._send_error(HTTPStatus.NOT_FOUND, 'Studio script module not found.')
                return
            if self._auth_required(path) and (not self._is_authorized()):
                self._send_unauthorized()
                return
            if method == 'GET' and path == '/':
                self._send_html(panel_html())
                return
            if method == 'GET' and path == '/api/info':
                self._send_json(api_info(self.auth_config, authorized=not self.auth_config.enabled or self._is_authorized()))
                return
            if method == 'GET' and path == '/api/template':
                self._send_json(api_template())
                return
            if self.route_registry.dispatch(self, method, path, parsed):
                return
            self._send_error(HTTPStatus.NOT_FOUND, 'Route not found.')
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ContextPackStaleError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except AcceptanceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except HumanReviewPackStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except AcceptanceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except HumanReviewPackNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AcceptanceValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except HumanReviewPackValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
