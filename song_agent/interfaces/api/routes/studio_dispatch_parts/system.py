from __future__ import annotations



from song_agent.interfaces.api.routes.program_registry import PROGRAM_ROUTE_REGISTRY

class StudioSystemDispatch:
    def _dispatch_studio_system(self, method, path, parsed) -> bool:
        if path == '/api/ga':
            self._handle_ga_route(method)
            return True
        if path == '/api/ga/check':
            self._handle_ga_check_route(method)
            return True
        if path == '/api/docs/index':
            self._handle_docs_index_route(method)
            return True
        if path == '/api/maintenance/status' or path.startswith('/api/maintenance/'):
            self._handle_maintenance_route(method, path)
            return True
        if path == '/api/unified-command-center-release-trains' or path.startswith('/api/unified-command-center-release-trains/'):
            self._handle_unified_command_center_release_trains_route(method, path)
            return True
        if PROGRAM_ROUTE_REGISTRY.dispatch(self, method, path):
            return True
        if path == '/api/unified-command-centers' or path.startswith('/api/unified-command-centers/'):
            self._handle_unified_command_centers_route(method, path)
            return True
        if path == '/api/provider':
            self._handle_provider_route(method)
            return True
        if path == '/api/provider/reset':
            self._handle_provider_reset(method)
            return True
        if path == '/api/provider/test':
            self._handle_provider_test(method)
            return True
        if path == '/api/renderer':
            self._handle_renderer_route(method)
            return True
        if path == '/api/renderer/reset':
            self._handle_renderer_reset(method)
            return True
        if path == '/api/renderer/test':
            self._handle_renderer_test(method)
            return True
        if path == '/api/audio/profiles' or path.startswith('/api/audio/profiles/'):
            self._handle_audio_profiles_route(method, path)
            return True
        if path == '/api/audio-lab' or path.startswith('/api/audio-lab/'):
            self._handle_audio_lab_route(method, path)
            return True
        if path == '/api/audio-fix-sprints' or path.startswith('/api/audio-fix-sprints/'):
            self._handle_audio_fix_sprint_route(method, path)
            return True
        if path == '/api/audio-campaigns' or path.startswith('/api/audio-campaigns/'):
            self._handle_audio_campaign_route(method, path)
            return True
        if path == '/api/audio-baselines' or path.startswith('/api/audio-baselines/'):
            self._handle_audio_baselines_route(method, path)
            return True
        if path == '/api/audio-quality-observatories' or path.startswith('/api/audio-quality-observatories/'):
            self._handle_audio_quality_observatories_route(method, path)
            return True
        if path == '/api/audio-quality-actions' or path.startswith('/api/audio-quality-actions/'):
            self._handle_audio_quality_actions_route(method, path)
            return True
        if path == '/api/mastering/profiles' or path.startswith('/api/mastering/profiles/'):
            self._handle_mastering_profiles_route(method, path)
            return True
        if path == '/api/audio-encoding/config' or path.startswith('/api/audio-encoding/config/') or path == '/api/audio-encoding/profiles' or path.startswith('/api/audio-encoding/profiles/'):
            self._handle_audio_encoding_route(method, path)
            return True
        if path == '/api/release-portfolio-audits' or path.startswith('/api/release-portfolio-audits/'):
            self._handle_release_portfolio_audits(method, path)
            return True
        if path == '/api/release-portfolio-governance-queues' or path.startswith('/api/release-portfolio-governance-queues/'):
            self._handle_release_portfolio_governance_queues(method, path)
            return True
        if path == '/api/public-trust-centers' or path.startswith('/api/public-trust-centers/'):
            self._handle_public_trust_centers(method, path)
            return True
        if path == '/api/trust-operations' or path.startswith('/api/trust-operations/'):
            self._handle_trust_operations(method, path)
            return True
        return False
