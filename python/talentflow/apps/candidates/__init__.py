# Candidates App - Candidate management
default_app_config = 'apps.candidates.apps.CandidatesConfig'

# Utility functions for convenience
from apps.candidates.utils import get_candidate_job_matches  # noqa: F401
