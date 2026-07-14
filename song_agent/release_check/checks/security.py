from song_agent.release_check_evidence_policy import run_evidence_policy_smoke
from song_agent.release_check.checks.legacy import delegated_check
from song_agent.release_check_lifecycle_kernel import run_lifecycle_kernel_smoke
from song_agent.release_check_verification_kernel import (
    run_kernel_adoption_smoke,
    run_shared_kernel_security_smoke,
    run_verification_kernel_smoke,
)


DOMAIN = "security"
GROUPS = frozenset({"security"})
TAGS = frozenset({"zip-security", "verification", "lifecycle", "evidence-graph", "policy"})
CALLABLES = {
    "_secret_scan": delegated_check("_secret_scan"),
    "_v1215_verification_kernel_smoke": run_verification_kernel_smoke,
    "_v1216_lifecycle_kernel_smoke": run_lifecycle_kernel_smoke,
    "_v1219_evidence_policy_smoke": run_evidence_policy_smoke,
    "_v1301_shared_kernel_security_smoke": run_shared_kernel_security_smoke,
    "_v132_kernel_adoption_smoke": run_kernel_adoption_smoke,
}
