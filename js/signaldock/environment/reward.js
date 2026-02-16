const PASS_THRESHOLDS = [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0];
const THRESHOLD_REWARDS = [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0];

const TOTAL_BUGS = 49;
const TOTAL_TESTS = 12213;

function sparseReward(passRate) {
  for (let i = PASS_THRESHOLDS.length - 1; i >= 0; i -= 1) {
    if (passRate >= PASS_THRESHOLDS[i]) return THRESHOLD_REWARDS[i];
  }
  return 0.0;
}

function totalBugs() {
  return TOTAL_BUGS;
}

function totalTests() {
  return TOTAL_TESTS;
}

// ---------------------------------------------------------------------------
// Bug Dependency Graph — documents prerequisite relationships between bugs.
// An agent cannot fully verify a fix for bug X until all bugs in its
// prerequisite list are also fixed, because failing prerequisites may mask
// or alter test outcomes for downstream bugs.
//
// Naming: <file>.<bugShortName>
// ---------------------------------------------------------------------------

const BUG_DEPENDENCY_GRAPH = Object.freeze({
  // --- scheduling.js (7 bugs) ---
  'scheduling.planWindowSort': [],
  'scheduling.canAcceptWithTideMutation': [],
  'scheduling.rollingWindowCanScheduleBoundary': [],
  'scheduling.rollingWindowUtilisationOffByOne': ['scheduling.rollingWindowCanScheduleBoundary'],
  'scheduling.reserveMsConversion': [],
  'scheduling.canAcceptWithTideDraftBoundary': ['scheduling.canAcceptWithTideMutation'],
  'scheduling.estimateTurnaroundDivisor': [],

  // --- routing.js (6 bugs) ---
  'routing.chooseRouteSortDesc': [],
  'routing.channelScoreCongestionSign': [],
  'routing.routeTableChannelCountDoubleCount': [],
  'routing.routeTableUpdateLatencyNullCheck': [],
  'routing.planMultiLegWrongLatency': ['routing.chooseRouteSortDesc'],
  'routing.estimateRouteCostFactor': ['routing.channelScoreCongestionSign'],

  // --- policy.js (5 bugs) ---
  'policy.isOperationalInverted': [],
  'policy.maxConcurrentAdds10': [],
  'policy.previousPolicyIndexNeg1': [],
  'policy.evaluateWithHistoryLookbackInverted': [],
  'policy.shouldDeescalateGtVsGte': [],

  // --- resilience.js (5 bugs) ---
  'resilience.replaySortDesc': [],
  'resilience.checkpointMergeMinVsMax': [],
  'resilience.circuitBreakerIsAllowedHalfOpen': [],
  'resilience.circuitBreakerFailureWithContextResets': ['resilience.circuitBreakerIsAllowedHalfOpen'],
  'resilience.snapshotDeltaReturnType': [],

  // --- security.js (5 bugs) ---
  'security.sanitisePathDotAllowed': [],
  'security.isAllowedOriginDefaultTrue': [],
  'security.verifySignatureOrShortCircuit': [],
  'security.verifyManifestChainClearsHash': ['security.verifySignatureOrShortCircuit'],
  'security.computeAccessLevelSubstring': [],

  // --- statistics.js (4 bugs) ---
  'statistics.percentileSortDesc': [],
  'statistics.meanDivByNPlus1': [],
  'statistics.percentileRangeSwap': ['statistics.percentileSortDesc'],
  'statistics.movingAverageNegWindow': [],

  // --- workflow.js (4 bugs) ---
  'workflow.activeCountTerminalVsActive': [],
  'workflow.isValidStateAndVsOr': [],
  'workflow.rollbackSetsWrongState': [],
  'workflow.transitionWithValidationArgOrder': [],

  // --- queue.js (5 bugs) ---
  'queue.shouldShedBoundary': [],
  'queue.priorityQueueSizeOffByOne': [],
  'queue.rateLimiterTryAcquireBoundary': [],
  'queue.estimateWaitTimePlusOne': [],
  'queue.queueHealthBoundary': [],

  // --- dispatch-ticket.js (4 bugs) ---
  'ticket.urgencyScoreSubtractVsAdd': [],
  'ticket.priorityBucketSeverityVsScore': ['ticket.urgencyScoreSubtractVsAdd'],
  'ticket.vesselRequiresSpecialHandlingInverted': [],
  'ticket.vesselClassifyBoundaries': [],

  // --- contracts.js (5 bugs: 1 existing + 4 new) ---
  'contracts.buildDependencyMatrixBidirectional': [],
  'contracts.dependencyDepthCountVsRecursive': [],
  'contracts.impactedServicesDirectOnly': ['contracts.dependencyDepthCountVsRecursive'],
  'contracts.isVersionCompatibleLexicographic': [],
  'contracts.deploymentWaveFlattenTo2': ['contracts.dependencyDepthCountVsRecursive'],
});

module.exports = {
  PASS_THRESHOLDS,
  THRESHOLD_REWARDS,
  sparseReward,
  totalBugs,
  totalTests,
  TOTAL_BUGS,
  TOTAL_TESTS,
  BUG_DEPENDENCY_GRAPH,
};
