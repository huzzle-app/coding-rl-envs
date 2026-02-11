# SignalDock - Greenfield Implementation Tasks

This document defines greenfield implementation tasks for the SignalDock maritime signal processing and dispatch platform. Each task requires implementing a new module from scratch while following the established architectural patterns.

## Prerequisites

- Familiarity with the existing codebase structure (`src/core/`, `src/models/`, `shared/contracts/`)
- Understanding of the maritime dispatch domain (vessels, berths, signals, routing)
- Node.js with CommonJS modules (`'use strict'` and `module.exports`)

## Test Command

```bash
npm test
```

---

## Task 1: AIS Signal Decoder

### Overview

Implement an Automatic Identification System (AIS) signal decoder that parses raw maritime radio signals into structured vessel position reports. AIS is the standard protocol for tracking vessel movements worldwide.

### Module Location

Create: `src/core/ais-decoder.js`

### Interface Contract

```javascript
'use strict';

/**
 * AIS message types supported by the decoder
 * @readonly
 * @enum {number}
 */
const AIS_MESSAGE_TYPES = Object.freeze({
  POSITION_REPORT_A: 1,    // Class A position report
  POSITION_REPORT_B: 2,    // Class A assigned scheduled position report
  POSITION_REPORT_C: 3,    // Class A interrogated position report
  BASE_STATION: 4,         // Base station report
  STATIC_DATA: 5,          // Static and voyage data
  ADDRESSED_BINARY: 6,     // Addressed binary message
  SAFETY_MESSAGE: 14,      // Safety-related broadcast
  POSITION_REPORT_B18: 18, // Class B position report
  POSITION_REPORT_B19: 19, // Class B extended position report
});

/**
 * Navigation status codes per ITU-R M.1371
 * @readonly
 * @enum {number}
 */
const NAV_STATUS = Object.freeze({
  UNDER_WAY_ENGINE: 0,
  AT_ANCHOR: 1,
  NOT_UNDER_COMMAND: 2,
  RESTRICTED_MANOEUVRABILITY: 3,
  CONSTRAINED_BY_DRAUGHT: 4,
  MOORED: 5,
  AGROUND: 6,
  FISHING: 7,
  UNDER_WAY_SAILING: 8,
  RESERVED_HSC: 9,
  RESERVED_WIG: 10,
  RESERVED_11: 11,
  RESERVED_12: 12,
  RESERVED_13: 13,
  AIS_SART: 14,
  NOT_DEFINED: 15,
});

/**
 * Decoded AIS position report
 * @typedef {Object} PositionReport
 * @property {number} mmsi - Maritime Mobile Service Identity (9 digits)
 * @property {number} messageType - AIS message type
 * @property {number} navStatus - Navigation status code
 * @property {number} rateOfTurn - Rate of turn (degrees/min, -127 to 127)
 * @property {number} speedOverGround - Speed in knots (0-102.2)
 * @property {boolean} positionAccuracy - True if DGPS, false if GPS
 * @property {number} longitude - Longitude in degrees (-180 to 180)
 * @property {number} latitude - Latitude in degrees (-90 to 90)
 * @property {number} courseOverGround - Course in degrees (0-359.9)
 * @property {number} trueHeading - Heading in degrees (0-359, 511 = N/A)
 * @property {number} timestamp - UTC second (0-59, 60-63 = special)
 * @property {number} receivedAt - Unix timestamp when signal was received
 */

/**
 * Decode a raw AIS NMEA sentence into a structured position report.
 *
 * @param {string} sentence - Raw NMEA sentence (e.g., "!AIVDM,1,1,,B,13u@DP0P00PqK7dN7T>0?wb60<00,0*73")
 * @returns {{ success: boolean, report?: PositionReport, error?: string }}
 */
function decodeAIS(sentence) { }

/**
 * Validate NMEA checksum for data integrity.
 *
 * @param {string} sentence - Complete NMEA sentence including checksum
 * @returns {boolean} True if checksum is valid
 */
function validateChecksum(sentence) { }

/**
 * Decode 6-bit ASCII armored payload into binary bits.
 *
 * @param {string} payload - Armored ASCII payload from NMEA sentence
 * @returns {string} Binary string of decoded bits
 */
function decodeSixBit(payload) { }

/**
 * Extract signed integer from bit string.
 *
 * @param {string} bits - Binary string
 * @param {number} start - Start bit position
 * @param {number} length - Number of bits to extract
 * @param {boolean} signed - Whether to interpret as signed
 * @returns {number}
 */
function extractBits(bits, start, length, signed) { }

/**
 * Calculate distance between two positions in nautical miles.
 *
 * @param {number} lat1 - Latitude of first point
 * @param {number} lon1 - Longitude of first point
 * @param {number} lat2 - Latitude of second point
 * @param {number} lon2 - Longitude of second point
 * @returns {number} Distance in nautical miles
 */
function haversineDistance(lat1, lon1, lat2, lon2) { }

/**
 * AIS signal buffer that aggregates multi-fragment messages.
 */
class AISBuffer {
  /**
   * @param {number} maxAge - Maximum age in ms before fragments expire
   */
  constructor(maxAge) { }

  /**
   * Add a fragment to the buffer.
   * @param {string} sentence - NMEA sentence
   * @returns {{ complete: boolean, report?: PositionReport }}
   */
  addFragment(sentence) { }

  /**
   * Purge expired incomplete messages.
   * @returns {number} Number of purged fragments
   */
  purgeExpired() { }

  /**
   * Get count of pending incomplete messages.
   * @returns {number}
   */
  pendingCount() { }
}

module.exports = {
  decodeAIS,
  validateChecksum,
  decodeSixBit,
  extractBits,
  haversineDistance,
  AISBuffer,
  AIS_MESSAGE_TYPES,
  NAV_STATUS,
};
```

### Required Models/Data Structures

1. **PositionReport** - Decoded vessel position (MMSI, lat/lon, speed, course, heading)
2. **AIS_MESSAGE_TYPES** - Enum of supported AIS message types (1, 2, 3, 5, 18, 19)
3. **NAV_STATUS** - Navigation status codes per ITU-R M.1371 standard

### Architectural Patterns to Follow

- Use `'use strict'` at file top
- Export via `module.exports = { ... }` (CommonJS)
- Use `Object.freeze()` for constants (see `src/models/dispatch-ticket.js`)
- Class-based state management (see `RouteTable` in `src/core/routing.js`)
- Pure functions for stateless operations
- Error returns as `{ success: false, error: string }` pattern

### Acceptance Criteria

1. **Unit Tests**: Create `tests/unit/ais-decoder.test.js` with coverage for:
   - Valid Type 1/2/3 position report decoding
   - Invalid checksum rejection
   - Multi-fragment message assembly
   - Edge cases (extreme coordinates, invalid MMSI)
   - Haversine distance calculation accuracy

2. **Integration Points**:
   - Output `PositionReport` compatible with `VesselManifest` linking via `vesselId` (MMSI)
   - Distance calculations usable by `estimateTransitTime()` in `routing.js`

3. **Coverage Requirements**:
   - All exported functions have at least one passing test
   - Edge case handling for malformed input
   - Minimum 80% line coverage for the module

---

## Task 2: Port Congestion Monitor

### Overview

Implement a real-time port congestion monitoring system that tracks berth utilization, vessel queue depths, and generates congestion alerts based on configurable thresholds.

### Module Location

Create: `src/core/congestion-monitor.js`

### Interface Contract

```javascript
'use strict';

/**
 * Congestion severity levels
 * @readonly
 * @enum {string}
 */
const CONGESTION_LEVEL = Object.freeze({
  CLEAR: 'clear',
  LIGHT: 'light',
  MODERATE: 'moderate',
  HEAVY: 'heavy',
  CRITICAL: 'critical',
});

/**
 * Alert types emitted by the monitor
 * @readonly
 * @enum {string}
 */
const ALERT_TYPE = Object.freeze({
  THRESHOLD_EXCEEDED: 'threshold_exceeded',
  QUEUE_OVERFLOW: 'queue_overflow',
  BERTH_SHORTAGE: 'berth_shortage',
  WAIT_TIME_SPIKE: 'wait_time_spike',
  RECOVERY: 'recovery',
});

/**
 * Port congestion snapshot
 * @typedef {Object} CongestionSnapshot
 * @property {string} portId - Port identifier
 * @property {number} timestamp - Snapshot timestamp
 * @property {number} totalBerths - Total available berths
 * @property {number} occupiedBerths - Currently occupied berths
 * @property {number} queueDepth - Vessels waiting for berth
 * @property {number} avgWaitMinutes - Average wait time in minutes
 * @property {string} level - Congestion level (CONGESTION_LEVEL)
 * @property {number} utilizationRatio - Berth utilization (0.0 - 1.0)
 */

/**
 * Congestion alert
 * @typedef {Object} CongestionAlert
 * @property {string} alertId - Unique alert identifier
 * @property {string} portId - Port identifier
 * @property {string} type - Alert type (ALERT_TYPE)
 * @property {string} level - Congestion level when alert was raised
 * @property {string} message - Human-readable alert message
 * @property {number} timestamp - Alert timestamp
 * @property {Object} metrics - Relevant metrics at time of alert
 */

/**
 * Calculate congestion level from utilization and queue metrics.
 *
 * @param {number} utilizationRatio - Berth utilization (0.0 - 1.0)
 * @param {number} queueDepth - Number of vessels waiting
 * @param {number} avgWaitMinutes - Average wait time
 * @returns {string} Congestion level
 */
function calculateCongestionLevel(utilizationRatio, queueDepth, avgWaitMinutes) { }

/**
 * Estimate queue clearance time based on current throughput.
 *
 * @param {number} queueDepth - Current queue depth
 * @param {number} avgServiceMinutes - Average berth service time
 * @param {number} availableBerths - Number of available berths
 * @returns {number} Estimated minutes to clear queue
 */
function estimateQueueClearance(queueDepth, avgServiceMinutes, availableBerths) { }

/**
 * Compute weighted congestion score for ranking ports.
 *
 * @param {CongestionSnapshot} snapshot - Port congestion snapshot
 * @param {{ utilization: number, queue: number, wait: number }} weights - Metric weights
 * @returns {number} Weighted score (0.0 - 100.0)
 */
function congestionScore(snapshot, weights) { }

/**
 * Real-time port congestion monitor.
 */
class PortCongestionMonitor {
  /**
   * @param {string} portId - Port identifier
   * @param {Object} config - Monitor configuration
   * @param {number} config.totalBerths - Total berth count
   * @param {number} config.warningThreshold - Utilization warning threshold (0.0-1.0)
   * @param {number} config.criticalThreshold - Utilization critical threshold (0.0-1.0)
   * @param {number} config.maxQueueDepth - Maximum acceptable queue depth
   * @param {number} config.maxWaitMinutes - Maximum acceptable wait time
   */
  constructor(portId, config) { }

  /**
   * Record a vessel entering the queue.
   * @param {string} vesselId - Vessel identifier
   * @param {number} timestamp - Entry timestamp
   * @returns {PortCongestionMonitor} this for chaining
   */
  enqueue(vesselId, timestamp) { }

  /**
   * Record a vessel being assigned to a berth.
   * @param {string} vesselId - Vessel identifier
   * @param {string} berthId - Berth identifier
   * @param {number} timestamp - Assignment timestamp
   * @returns {{ waitMinutes: number, queuePosition: number }}
   */
  assignBerth(vesselId, berthId, timestamp) { }

  /**
   * Record a vessel departing from a berth.
   * @param {string} vesselId - Vessel identifier
   * @param {string} berthId - Berth identifier
   * @param {number} timestamp - Departure timestamp
   * @returns {{ serviceMinutes: number }}
   */
  releaseBerth(vesselId, berthId, timestamp) { }

  /**
   * Get current congestion snapshot.
   * @returns {CongestionSnapshot}
   */
  snapshot() { }

  /**
   * Get all unacknowledged alerts.
   * @returns {CongestionAlert[]}
   */
  pendingAlerts() { }

  /**
   * Acknowledge an alert.
   * @param {string} alertId - Alert to acknowledge
   * @returns {boolean} True if alert was found and acknowledged
   */
  acknowledgeAlert(alertId) { }

  /**
   * Get historical snapshots within time range.
   * @param {number} fromTimestamp - Start of range
   * @param {number} toTimestamp - End of range
   * @returns {CongestionSnapshot[]}
   */
  history(fromTimestamp, toTimestamp) { }

  /**
   * Register callback for alert notifications.
   * @param {function(CongestionAlert): void} callback - Alert handler
   */
  onAlert(callback) { }

  /**
   * Reset monitor state (for testing).
   */
  reset() { }
}

/**
 * Aggregate congestion across multiple ports.
 */
class FleetCongestionAggregator {
  /**
   * Register a port monitor.
   * @param {PortCongestionMonitor} monitor - Port monitor instance
   */
  registerPort(monitor) { }

  /**
   * Get aggregated snapshot across all ports.
   * @returns {{ ports: CongestionSnapshot[], totalUtilization: number, totalQueueDepth: number }}
   */
  aggregateSnapshot() { }

  /**
   * Rank ports by congestion (most congested first).
   * @returns {CongestionSnapshot[]}
   */
  rankByCongestion() { }

  /**
   * Find least congested port with available capacity.
   * @param {number} minBerthsRequired - Minimum available berths needed
   * @returns {CongestionSnapshot|null}
   */
  findLeastCongested(minBerthsRequired) { }
}

module.exports = {
  calculateCongestionLevel,
  estimateQueueClearance,
  congestionScore,
  PortCongestionMonitor,
  FleetCongestionAggregator,
  CONGESTION_LEVEL,
  ALERT_TYPE,
};
```

### Required Models/Data Structures

1. **CongestionSnapshot** - Point-in-time port congestion state
2. **CongestionAlert** - Alert raised when thresholds are exceeded
3. **CONGESTION_LEVEL** - Enum of congestion severity levels
4. **ALERT_TYPE** - Enum of alert categories

### Architectural Patterns to Follow

- Event callback pattern for alerts (see `onAlert` method)
- Sliding window metrics (see `ResponseTimeTracker` in `statistics.js`)
- Threshold-based status classification (see `queueHealth` in `queue.js`)
- Chained method returns for builder pattern (see `BerthSlot.reserve()`)

### Acceptance Criteria

1. **Unit Tests**: Create `tests/unit/congestion-monitor.test.js` with coverage for:
   - Congestion level calculation at all thresholds
   - Queue operations (enqueue, assign, release)
   - Alert generation and acknowledgment
   - Historical snapshot retrieval
   - Fleet aggregation and ranking

2. **Integration Points**:
   - `BerthSlot` from `scheduling.js` for berth state tracking
   - `queueHealth` from `queue.js` for status classification consistency
   - `ResponseTimeTracker` from `statistics.js` for wait time tracking

3. **Coverage Requirements**:
   - Threshold boundary tests (exact threshold values)
   - Alert callback invocation verification
   - Minimum 80% line coverage for the module

---

## Task 3: Vessel ETA Predictor

### Overview

Implement a vessel ETA (Estimated Time of Arrival) prediction system that combines AIS position data, route information, and historical voyage patterns to provide accurate arrival forecasts with confidence intervals.

### Module Location

Create: `src/core/eta-predictor.js`

### Interface Contract

```javascript
'use strict';

/**
 * Prediction confidence levels
 * @readonly
 * @enum {string}
 */
const CONFIDENCE_LEVEL = Object.freeze({
  HIGH: 'high',       // > 90% confidence
  MEDIUM: 'medium',   // 70-90% confidence
  LOW: 'low',         // 50-70% confidence
  UNCERTAIN: 'uncertain', // < 50% confidence
});

/**
 * Factors that can affect ETA predictions
 * @readonly
 * @enum {string}
 */
const ETA_FACTOR = Object.freeze({
  WEATHER: 'weather',
  TRAFFIC: 'traffic',
  PORT_CONGESTION: 'port_congestion',
  SPEED_DEVIATION: 'speed_deviation',
  ROUTE_DEVIATION: 'route_deviation',
  HISTORICAL_VARIANCE: 'historical_variance',
});

/**
 * Vessel position for ETA calculation
 * @typedef {Object} VesselPosition
 * @property {string} vesselId - Vessel identifier (MMSI)
 * @property {number} latitude - Current latitude
 * @property {number} longitude - Current longitude
 * @property {number} speedOverGround - Current speed in knots
 * @property {number} courseOverGround - Current course in degrees
 * @property {number} timestamp - Position timestamp
 */

/**
 * ETA prediction result
 * @typedef {Object} ETAPrediction
 * @property {string} vesselId - Vessel identifier
 * @property {string} destinationPortId - Destination port
 * @property {number} predictedETA - Predicted arrival timestamp
 * @property {number} earliestETA - Earliest possible arrival
 * @property {number} latestETA - Latest possible arrival
 * @property {number} remainingDistanceNm - Remaining distance in nautical miles
 * @property {number} confidencePercent - Confidence percentage (0-100)
 * @property {string} confidenceLevel - Confidence level category
 * @property {string[]} factors - Factors affecting prediction
 * @property {number} calculatedAt - Prediction calculation timestamp
 */

/**
 * Waypoint on a vessel's route
 * @typedef {Object} Waypoint
 * @property {number} latitude - Waypoint latitude
 * @property {number} longitude - Waypoint longitude
 * @property {string} name - Waypoint name (optional)
 */

/**
 * Calculate simple ETA based on distance and speed.
 *
 * @param {number} distanceNm - Distance in nautical miles
 * @param {number} speedKnots - Speed in knots
 * @returns {number} Time in hours
 */
function calculateSimpleETA(distanceNm, speedKnots) { }

/**
 * Calculate remaining distance along a route.
 *
 * @param {VesselPosition} position - Current vessel position
 * @param {Waypoint[]} waypoints - Remaining waypoints to destination
 * @returns {number} Total remaining distance in nautical miles
 */
function calculateRemainingDistance(position, waypoints) { }

/**
 * Apply speed adjustment factor based on conditions.
 *
 * @param {number} baseSpeedKnots - Base speed
 * @param {{ weather: number, traffic: number, fatigue: number }} factors - Adjustment factors (0.0-1.0)
 * @returns {number} Adjusted speed in knots
 */
function adjustSpeedForConditions(baseSpeedKnots, factors) { }

/**
 * Calculate confidence interval width based on data quality.
 *
 * @param {number} hoursRemaining - Hours until predicted arrival
 * @param {number} positionAge - Age of last position in seconds
 * @param {number} historicalVariance - Historical voyage time variance
 * @returns {{ lowerBoundHours: number, upperBoundHours: number, confidencePercent: number }}
 */
function calculateConfidenceInterval(hoursRemaining, positionAge, historicalVariance) { }

/**
 * ETA prediction engine with historical learning.
 */
class ETAPredictor {
  /**
   * @param {Object} config - Predictor configuration
   * @param {number} config.defaultSpeedKnots - Default speed assumption
   * @param {number} config.maxPositionAgeSeconds - Maximum acceptable position age
   * @param {number} config.historicalWeight - Weight for historical data (0.0-1.0)
   */
  constructor(config) { }

  /**
   * Register a port with its coordinates.
   * @param {string} portId - Port identifier
   * @param {number} latitude - Port latitude
   * @param {number} longitude - Port longitude
   * @returns {ETAPredictor} this for chaining
   */
  registerPort(portId, latitude, longitude) { }

  /**
   * Update vessel position.
   * @param {VesselPosition} position - Latest position report
   * @returns {ETAPredictor} this for chaining
   */
  updatePosition(position) { }

  /**
   * Set route waypoints for a vessel.
   * @param {string} vesselId - Vessel identifier
   * @param {Waypoint[]} waypoints - Route waypoints
   * @returns {ETAPredictor} this for chaining
   */
  setRoute(vesselId, waypoints) { }

  /**
   * Record completed voyage for historical learning.
   * @param {string} vesselId - Vessel identifier
   * @param {string} originPortId - Origin port
   * @param {string} destinationPortId - Destination port
   * @param {number} actualDurationHours - Actual voyage duration
   */
  recordVoyage(vesselId, originPortId, destinationPortId, actualDurationHours) { }

  /**
   * Predict ETA for a vessel to a destination.
   * @param {string} vesselId - Vessel identifier
   * @param {string} destinationPortId - Destination port
   * @returns {ETAPrediction|null} Prediction or null if insufficient data
   */
  predict(vesselId, destinationPortId) { }

  /**
   * Get all active predictions.
   * @returns {ETAPrediction[]}
   */
  allPredictions() { }

  /**
   * Get prediction accuracy metrics.
   * @returns {{ meanErrorHours: number, stdDevHours: number, predictionCount: number }}
   */
  accuracyMetrics() { }

  /**
   * Apply external condition adjustments.
   * @param {string} vesselId - Vessel identifier
   * @param {Object} conditions - Condition factors
   * @param {number} conditions.weatherFactor - Weather impact (0.5-1.5)
   * @param {number} conditions.trafficFactor - Traffic impact (0.5-1.5)
   * @param {number} conditions.portCongestionMinutes - Expected port delay
   */
  applyConditions(vesselId, conditions) { }

  /**
   * Clear all data (for testing).
   */
  reset() { }
}

/**
 * Voyage history store for historical pattern analysis.
 */
class VoyageHistoryStore {
  /**
   * @param {number} maxRecords - Maximum records to retain per route
   */
  constructor(maxRecords) { }

  /**
   * Add a completed voyage.
   * @param {string} routeKey - Route identifier (origin:destination)
   * @param {number} durationHours - Voyage duration
   * @param {number} timestamp - Voyage completion timestamp
   */
  addVoyage(routeKey, durationHours, timestamp) { }

  /**
   * Get historical statistics for a route.
   * @param {string} routeKey - Route identifier
   * @returns {{ avgDurationHours: number, stdDevHours: number, sampleCount: number }|null}
   */
  getRouteStats(routeKey) { }

  /**
   * Get variance for a route.
   * @param {string} routeKey - Route identifier
   * @returns {number} Variance in hours, or default if no history
   */
  getVariance(routeKey) { }

  /**
   * Purge old records beyond retention period.
   * @param {number} maxAgeMs - Maximum age in milliseconds
   * @returns {number} Number of purged records
   */
  purgeOld(maxAgeMs) { }
}

module.exports = {
  calculateSimpleETA,
  calculateRemainingDistance,
  adjustSpeedForConditions,
  calculateConfidenceInterval,
  ETAPredictor,
  VoyageHistoryStore,
  CONFIDENCE_LEVEL,
  ETA_FACTOR,
};
```

### Required Models/Data Structures

1. **VesselPosition** - Current vessel position from AIS
2. **ETAPrediction** - Prediction result with confidence intervals
3. **Waypoint** - Route waypoint coordinates
4. **CONFIDENCE_LEVEL** - Prediction confidence categories
5. **ETA_FACTOR** - Factors affecting predictions

### Architectural Patterns to Follow

- Configuration object in constructor (see `RollingWindowScheduler`)
- Builder pattern with `return this` (see `RouteTable.register()`)
- Statistics functions from `statistics.js` for variance calculations
- Haversine formula consistent with `ais-decoder.js` (if implemented)

### Acceptance Criteria

1. **Unit Tests**: Create `tests/unit/eta-predictor.test.js` with coverage for:
   - Simple ETA calculation accuracy
   - Distance calculation with multiple waypoints
   - Confidence interval widening with uncertainty
   - Historical learning integration
   - Condition factor application

2. **Integration Points**:
   - Position input compatible with `PositionReport` from AIS decoder
   - Statistical functions compatible with `statistics.js`
   - Port registration compatible with berth scheduling

3. **Coverage Requirements**:
   - All confidence level thresholds tested
   - Edge cases (zero speed, stale position, no history)
   - Prediction accuracy tracking
   - Minimum 80% line coverage for the module

---

## General Guidelines

### File Structure

```
src/
  core/
    ais-decoder.js      # Task 1
    congestion-monitor.js  # Task 2
    eta-predictor.js    # Task 3
tests/
  unit/
    ais-decoder.test.js
    congestion-monitor.test.js
    eta-predictor.test.js
```

### Testing Pattern

Follow the existing test pattern using Node.js built-in test runner:

```javascript
const test = require('node:test');
const assert = require('node:assert/strict');
const { functionName, ClassName } = require('../../src/core/module-name');

test('functionName does expected behavior', () => {
  const result = functionName(input);
  assert.equal(result, expected);
});

test('ClassName method handles edge case', () => {
  const instance = new ClassName(config);
  const result = instance.method(input);
  assert.deepEqual(result, expected);
});
```

### Error Handling

- Return error objects `{ success: false, error: 'reason' }` rather than throwing
- Use null returns for "not found" cases
- Validate inputs and return early with error indicators

### Constants

- Use `Object.freeze()` for all enum-like constants
- Define constants at module scope above functions
- Export constants for use by other modules
