from __future__ import annotations

from .trust_parts.dependencies import *

from .trust_parts.part_001 import *

from .trust_parts.part_002 import *

from .trust_parts.part_003 import *

from .trust_parts.part_004 import *

from .trust_parts.part_005 import *

from .trust_parts.part_006 import *

from .trust_parts.part_007 import *

from .trust_parts.part_008 import *

from .trust_parts.part_009 import *

from .trust_parts.part_010 import *

from .trust_parts.part_011 import *

from .trust_parts.part_012 import *

from .trust_parts.part_013 import *

from .trust_parts.part_014 import *

from .trust_parts.part_015 import *

from .trust_parts.part_016 import *

from .trust_parts.part_017 import *

from .trust_parts.part_018 import *

SPECS = (
    CommandSpec(name='verify-release-portfolio-audit-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_audit_package, help='Verify Release Portfolio Audit Package', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_package, help='Verify Release Portfolio Governance Package', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-archive-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_archive_package, help='Verify Release Portfolio Governance Archive Package', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-audit-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_audit_package, help='Verify Release Portfolio Governance Audit Package', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-reviewer-pack', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_reviewer_pack, help='Verify Release Portfolio Governance Reviewer Pack', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-final-board', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_final_board, help='Verify Release Portfolio Governance Final Board', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-evidence-vault', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_evidence_vault, help='Verify Release Portfolio Governance Evidence Vault', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-attestation', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_attestation, help='Verify Release Portfolio Governance Attestation', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-attestation-registry', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_attestation_registry, help='Verify Release Portfolio Governance Attestation Registry', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-attestation-portal', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_attestation_portal, help='Verify Release Portfolio Governance Attestation Portal', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-attestation-portal-review-pack', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_attestation_portal_review_pack, help='Verify Release Portfolio Governance Attestation Portal Review Pack', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-attestation-portal-response', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_attestation_portal_response, help='Verify Release Portfolio Governance Attestation Portal Response', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-attestation-accepted-evidence', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_attestation_accepted_evidence, help='Verify Release Portfolio Governance Attestation Accepted Evidence', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-attestation-transparency', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_attestation_transparency, help='Verify Release Portfolio Governance Attestation Transparency', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-attestation-transparency-acknowledgement', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_attestation_transparency_acknowledgement, help='Verify Release Portfolio Governance Attestation Transparency Acknowledgement', group='trust'),
    CommandSpec(name='verify-public-trust-center-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_package, help='Verify Public Trust Center Package', group='trust'),
    CommandSpec(name='verify-public-trust-center-anchor-registry-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_anchor_registry_package, help='Verify Public Trust Center Anchor Registry Package', group='trust'),
    CommandSpec(name='verify-public-trust-center-anchor-transparency-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_anchor_transparency_package, help='Verify Public Trust Center Anchor Transparency Package', group='trust'),
    CommandSpec(name='verify-public-trust-center-distribution-kit-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_distribution_kit_package, help='Verify Public Trust Center Distribution Kit Package', group='trust'),
    CommandSpec(name='verify-public-trust-center-distribution-kit-accepted-evidence-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_distribution_kit_accepted_evidence_package, help='Verify Public Trust Center Distribution Kit Accepted Evidence Package', group='trust'),
    CommandSpec(name='verify-public-trust-center-acceptance-board-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_acceptance_board_package, help='Verify Public Trust Center Acceptance Board Package', group='trust'),
    CommandSpec(name='verify-public-trust-center-acceptance-board-signoff-archive-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_acceptance_board_signoff_archive_package, help='Verify Public Trust Center Acceptance Board Signoff Archive Package', group='trust'),
    CommandSpec(name='verify-public-trust-center-publication-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_publication_package, help='Verify Public Trust Center Publication Package', group='trust'),
    CommandSpec(name='verify-public-trust-center-publication-mirror', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_publication_mirror, help='Verify Public Trust Center Publication Mirror', group='trust'),
    CommandSpec(name='verify-public-trust-center-publication-monitoring-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_publication_monitoring_package, help='Verify Public Trust Center Publication Monitoring Package', group='trust'),
    CommandSpec(name='verify-trust-operations-hub-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_hub_package, help='Verify Trust Operations Hub Package', group='trust'),
    CommandSpec(name='verify-trust-operations-assurance-watch-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_assurance_watch_package, help='Verify Trust Operations Assurance Watch Package', group='trust'),
    CommandSpec(name='verify-trust-operations-assurance-watch-signoff-archive-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_assurance_watch_signoff_archive_package, help='Verify Trust Operations Assurance Watch Signoff Archive Package', group='trust'),
    CommandSpec(name='verify-trust-operations-final-handoff-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_final_handoff_package, help='Verify Trust Operations Final Handoff Package', group='trust'),
    CommandSpec(name='verify-trust-operations-assurance-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_assurance_package, help='Verify Trust Operations Assurance Package', group='trust'),
    CommandSpec(name='verify-trust-operations-control-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_control_package, help='Verify Trust Operations Control Package', group='trust'),
    CommandSpec(name='verify-trust-operations-control-signoff-archive-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_control_signoff_archive_package, help='Verify Trust Operations Control Signoff Archive Package', group='trust'),
    CommandSpec(name='verify-trust-operations-incident-knowledge-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_incident_knowledge_package, help='Verify Trust Operations Incident Knowledge Package', group='trust'),
    CommandSpec(name='verify-trust-operations-hub-incident-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_hub_incident_package, help='Verify Trust Operations Hub Incident Package', group='trust'),
    CommandSpec(name='verify-trust-operations-hub-runbook-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_hub_runbook_package, help='Verify Trust Operations Hub Runbook Package', group='trust'),
    CommandSpec(name='release-portfolio-audit', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_audit, help='Release Portfolio Audit', group='trust'),
    CommandSpec(name='release-portfolio-governance-queue', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_queue, help='Release Portfolio Governance Queue', group='trust'),
    CommandSpec(name='release-portfolio-governance-signoff', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_signoff, help='Release Portfolio Governance Signoff', group='trust'),
    CommandSpec(name='release-portfolio-governance-audit', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_audit, help='Release Portfolio Governance Audit', group='trust'),
    CommandSpec(name='release-portfolio-governance-reviewer-pack', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_reviewer_pack, help='Release Portfolio Governance Reviewer Pack', group='trust'),
    CommandSpec(name='release-portfolio-governance-final-board', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_final_board, help='Release Portfolio Governance Final Board', group='trust'),
    CommandSpec(name='release-portfolio-governance-evidence-vault', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_evidence_vault, help='Release Portfolio Governance Evidence Vault', group='trust'),
    CommandSpec(name='release-portfolio-governance-attestation', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_attestation, help='Release Portfolio Governance Attestation', group='trust'),
    CommandSpec(name='release-portfolio-governance-attestation-registry', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_attestation_registry, help='Release Portfolio Governance Attestation Registry', group='trust'),
    CommandSpec(name='release-portfolio-governance-attestation-portal', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_attestation_portal, help='Release Portfolio Governance Attestation Portal', group='trust'),
    CommandSpec(name='release-portfolio-governance-attestation-portal-review', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_attestation_portal_review, help='Release Portfolio Governance Attestation Portal Review', group='trust'),
    CommandSpec(name='release-portfolio-governance-attestation-accepted-evidence', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_attestation_accepted_evidence, help='Release Portfolio Governance Attestation Accepted Evidence', group='trust'),
    CommandSpec(name='release-portfolio-governance-attestation-transparency', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_attestation_transparency, help='Release Portfolio Governance Attestation Transparency', group='trust'),
    CommandSpec(name='release-portfolio-governance-attestation-transparency-acknowledgement', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_attestation_transparency_acknowledgement, help='Release Portfolio Governance Attestation Transparency Acknowledgement', group='trust'),
    CommandSpec(name='public-trust-center-publication', parser=build_acceptance_analytics_parser, handler=handle_public_trust_center_publication, help='Public Trust Center Publication', group='trust'),
    CommandSpec(name='public-trust-center-publication-monitor', parser=build_acceptance_analytics_parser, handler=handle_public_trust_center_publication_monitor, help='Public Trust Center Publication Monitor', group='trust'),
    CommandSpec(name='trust-operations-hub', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_hub, help='Trust Operations Hub', group='trust'),
    CommandSpec(name='trust-operations-assurance-watch', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_assurance_watch, help='Trust Operations Assurance Watch', group='trust'),
    CommandSpec(name='trust-operations-assurance-watch-signoff', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_assurance_watch_signoff, help='Trust Operations Assurance Watch Signoff', group='trust'),
    CommandSpec(name='trust-operations-final-readiness', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_final_readiness, help='Trust Operations Final Readiness', group='trust'),
    CommandSpec(name='trust-operations-controls', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_controls, help='Trust Operations Controls', group='trust'),
    CommandSpec(name='trust-operations-assurance', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_assurance, help='Trust Operations Assurance', group='trust'),
    CommandSpec(name='trust-operations-control-signoff', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_control_signoff, help='Trust Operations Control Signoff', group='trust'),
    CommandSpec(name='trust-operations-hub-runbook', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_hub_runbook, help='Trust Operations Hub Runbook', group='trust'),
    CommandSpec(name='trust-operations-hub-incidents', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_hub_incidents, help='Trust Operations Hub Incidents', group='trust'),
    CommandSpec(name='trust-operations-incident-knowledge', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_incident_knowledge, help='Trust Operations Incident Knowledge', group='trust'),
    CommandSpec(name='public-trust-center', parser=build_acceptance_analytics_parser, handler=handle_public_trust_center, help='Public Trust Center', group='trust'),
)

for _spec in SPECS:
    _spec.parser.__module__ = __name__
    _spec.handler.__module__ = __name__
