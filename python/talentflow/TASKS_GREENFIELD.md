# TalentFlow - Greenfield Tasks

These tasks require implementing new modules from scratch, following existing architectural patterns in the codebase.

---

## Task 1: Implement Onboarding Workflow Service

**Type:** Greenfield Module

**Description:**
Create a new OnboardingService that manages the post-hire onboarding workflow for candidates who have accepted offers. This service should orchestrate document collection, equipment provisioning requests, system access setup, and first-day scheduling.

The service must integrate with existing TalentFlow patterns: Django models, Celery tasks for async operations, and the existing notification infrastructure.

**Interface Contract:**
```python
class OnboardingService:
    def start_onboarding(self, candidate_id: int, start_date: date) -> OnboardingWorkflow:
        """Initialize onboarding workflow for a hired candidate."""

    def get_workflow_status(self, workflow_id: int) -> WorkflowStatus:
        """Get current status of all onboarding steps."""

    def complete_step(self, workflow_id: int, step_type: str, data: dict) -> bool:
        """Mark an onboarding step as complete with associated data."""

    def get_pending_tasks(self, assignee_id: int) -> List[OnboardingTask]:
        """Get all pending onboarding tasks assigned to a user."""

    def send_reminder(self, workflow_id: int, step_type: str) -> bool:
        """Send reminder notification for incomplete step."""
```

**Required Models:**
- `OnboardingWorkflow` - Tracks overall onboarding state
- `OnboardingStep` - Individual steps (documents, equipment, access, etc.)
- `OnboardingTask` - Assignable tasks for HR/IT staff

**Acceptance Criteria:**
- All interface methods implemented with proper error handling
- Django models with appropriate fields, indexes, and relationships
- Celery tasks for async reminder scheduling
- Integration with existing `Candidate` and `Company` models
- Unit tests with >80% coverage
- Follows existing code style and patterns in `apps/` directory

**Test Command:**
```bash
python manage.py test apps.onboarding.tests
```

---

## Task 2: Implement Skills Assessment Engine

**Type:** Greenfield Module

**Description:**
Create a SkillsAssessmentEngine that administers and scores technical assessments for candidates. The engine should support multiple question types, timed assessments, and automated scoring with anti-cheating measures.

This integrates with the existing matching system to update candidate scores based on assessment performance.

**Interface Contract:**
```python
class SkillsAssessmentEngine:
    def create_assessment(self, job_id: int, config: AssessmentConfig) -> Assessment:
        """Create a new assessment linked to a job posting."""

    def start_attempt(self, assessment_id: int, candidate_id: int) -> AssessmentAttempt:
        """Start a timed assessment attempt for a candidate."""

    def submit_answer(self, attempt_id: int, question_id: int, answer: Any) -> bool:
        """Submit answer for a question within time limit."""

    def complete_attempt(self, attempt_id: int) -> AssessmentResult:
        """Finalize attempt and calculate scores."""

    def get_candidate_results(self, candidate_id: int) -> List[AssessmentResult]:
        """Get all assessment results for a candidate."""

    def generate_assessment_report(self, attempt_id: int) -> AssessmentReport:
        """Generate detailed report with question-by-question breakdown."""
```

**Required Models:**
- `Assessment` - Assessment configuration and questions
- `Question` - Individual questions with type, correct answer, points
- `AssessmentAttempt` - Candidate's attempt with timing
- `Answer` - Submitted answers with timestamps
- `AssessmentResult` - Calculated scores and percentiles

**Acceptance Criteria:**
- Support for multiple choice, coding, and free-text questions
- Time tracking with automatic submission on expiry
- Scoring algorithm with partial credit support
- Anti-cheating: tab-switch detection, time anomaly flagging
- Integration with `apps/jobs/matching.py` to update match scores
- Celery task for async report generation
- Unit tests covering scoring edge cases

**Test Command:**
```bash
python manage.py test apps.assessments.tests
```

---

## Task 3: Implement Employee Referral Program Service

**Type:** Greenfield Module

**Description:**
Create a ReferralService that manages an employee referral program. Employees can refer candidates, track referral status, and receive rewards when referrals are hired. The service should handle duplicate detection, referral attribution, and reward calculations.

**Interface Contract:**
```python
class ReferralService:
    def submit_referral(
        self,
        referrer_id: int,
        candidate_email: str,
        job_id: int,
        relationship: str,
        notes: str
    ) -> Referral:
        """Submit a new referral, checking for duplicates."""

    def get_referrer_dashboard(self, referrer_id: int) -> ReferralDashboard:
        """Get referral statistics and pending rewards for an employee."""

    def update_referral_status(self, referral_id: int, status: str) -> Referral:
        """Update referral status as candidate progresses."""

    def calculate_reward(self, referral_id: int) -> RewardCalculation:
        """Calculate reward based on job level and referral policy."""

    def process_reward(self, referral_id: int) -> RewardPayment:
        """Process reward payment after retention period."""

    def get_referral_leaderboard(self, company_id: int, period: str) -> List[LeaderboardEntry]:
        """Get top referrers for gamification."""
```

**Required Models:**
- `Referral` - Referral record with status tracking
- `ReferralPolicy` - Company-specific reward policies
- `ReferralReward` - Pending and paid rewards

**Acceptance Criteria:**
- Duplicate detection by email within company
- Attribution tracking when referred candidate applies
- Configurable reward tiers by job level/department
- Retention period enforcement before reward payout
- Email notifications at key status changes
- Leaderboard with monthly/quarterly/yearly views
- Unit tests including duplicate and edge cases

**Test Command:**
```bash
python manage.py test apps.referrals.tests
```
