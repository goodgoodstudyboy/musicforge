"""Release engineering package.

The top-level ``release_check_*`` modules remain compatibility facades until
the v13 cutover. New code should import this package directly.
"""

from song_agent.release_check.matrix import ReleaseCheckDefinition, ReleaseCheckMatrixError
from song_agent.release_check.runner import CheckResult, ReleaseCheckReport, run_release_check_matrix

__all__ = [
    "CheckResult",
    "ReleaseCheckDefinition",
    "ReleaseCheckMatrixError",
    "ReleaseCheckReport",
    "run_release_check_matrix",
]
