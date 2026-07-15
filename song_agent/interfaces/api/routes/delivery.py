from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

from song_agent.application.release_signoff import ReleaseSignoffApplication

from .delivery_parts.distribution_profiles import DeliveryRoutesDistributionProfiles

from .delivery_parts.release import DeliveryRoutesRelease

from .delivery_parts.release_operations import DeliveryRoutesReleaseOperations

from .delivery_parts.release_operations_reviewer_pack import DeliveryRoutesReleaseOperationsReviewerPack

from .delivery_parts.distribution import DeliveryRoutesDistribution

from .delivery_parts.get_or_refresh_distribution_qa import DeliveryRoutesGetOrRefreshDistributionQa

from .delivery_parts.submission import DeliveryRoutesSubmission

from .delivery_parts.get_or_refresh_submission_qa import DeliveryRoutesGetOrRefreshSubmissionQa

class DeliveryRoutes(DeliveryRoutesDistributionProfiles, DeliveryRoutesRelease, DeliveryRoutesReleaseOperations, DeliveryRoutesReleaseOperationsReviewerPack, DeliveryRoutesDistribution, DeliveryRoutesGetOrRefreshDistributionQa, DeliveryRoutesSubmission, DeliveryRoutesGetOrRefreshSubmissionQa):
    def _handle_release_signoff(self, method: str, release_id: str) -> None:
        ReleaseSignoffApplication(self).execute(method, release_id)
