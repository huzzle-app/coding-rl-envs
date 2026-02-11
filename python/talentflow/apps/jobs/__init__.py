# Jobs App - Job postings and matching
default_app_config = 'apps.jobs.apps.JobsConfig'

# Import matching utilities
from apps.jobs.matching import calculate_skill_match_score  # noqa: F401
