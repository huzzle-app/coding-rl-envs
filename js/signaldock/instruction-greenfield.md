# SignalDock - Greenfield Implementation Tasks

## Overview
SignalDock supports 3 greenfield implementation tasks that build new modules from scratch. These tasks require designing and implementing new services that integrate with the existing maritime dispatch platform architecture while following established patterns for module structure, error handling, and testing.

## Environment
- **Language**: JavaScript (Node.js)
- **Infrastructure**: Maritime signal processing and dispatch coordination platform with routing, scheduling, resilience, security, and policy modules
- **Difficulty**: Hyper-Principal (70-140h expected)

## Tasks

### Task 1: AIS Signal Decoder (Greenfield Implementation)
**Module Location**: `src/core/ais-decoder.js`

Implement an Automatic Identification System (AIS) signal decoder that parses raw maritime radio NMEA sentences into structured vessel position reports. The decoder must support multiple AIS message types (Type 1, 2, 3, 5, 18, 19), validate NMEA checksums, decode 6-bit ASCII armored payloads, extract signed integers from bit strings, and calculate distances using the haversine formula. Includes an `AISBuffer` class for assembling multi-fragment messages with configurable expiration.

**Key Interfaces**:
- `decodeAIS(sentence)` → `{ success, report?, error? }`
- `validateChecksum(sentence)` → boolean
- `decodeSixBit(payload)` → binary string
- `extractBits(bits, start, length, signed)` → number
- `haversineDistance(lat1, lon1, lat2, lon2)` → nautical miles
- `AISBuffer` class with `addFragment()`, `purgeExpired()`, `pendingCount()`

**Data Structures**:
- `PositionReport` — Decoded vessel position with MMSI, coordinates, speed, course, heading, navigation status
- `AIS_MESSAGE_TYPES` — Enum of supported message types
- `NAV_STATUS` — Navigation status codes per ITU-R M.1371 standard

### Task 2: Port Congestion Monitor (Greenfield Implementation)
**Module Location**: `src/core/congestion-monitor.js`

Implement a real-time port congestion monitoring system that tracks berth utilization, vessel queue depths, and generates congestion alerts based on configurable thresholds. The monitor must calculate congestion levels, estimate queue clearance times, and compute weighted congestion scores for ranking ports. Includes a `PortCongestionMonitor` class for single-port tracking and a `FleetCongestionAggregator` for multi-port analysis with alert callbacks and historical snapshot retrieval.

**Key Interfaces**:
- `calculateCongestionLevel(utilization, queueDepth, avgWaitMinutes)` → level
- `estimateQueueClearance(queueDepth, avgServiceMinutes, availableBerths)` → minutes
- `congestionScore(snapshot, weights)` → score (0-100)
- `PortCongestionMonitor` with queue operations, alert management, history retrieval, and callbacks
- `FleetCongestionAggregator` with registration, aggregation, ranking, and capacity search

**Data Structures**:
- `CongestionSnapshot` — Point-in-time port congestion state with utilization and queue metrics
- `CongestionAlert` — Alert raised when thresholds exceeded with type, level, message, and metrics
- `CONGESTION_LEVEL` — Enum (clear, light, moderate, heavy, critical)
- `ALERT_TYPE` — Enum (threshold_exceeded, queue_overflow, berth_shortage, wait_time_spike, recovery)

### Task 3: Vessel ETA Predictor (Greenfield Implementation)
**Module Location**: `src/core/eta-predictor.js`

Implement a vessel ETA (Estimated Time of Arrival) prediction engine that combines AIS position data, route information, and historical voyage patterns to provide arrival forecasts with confidence intervals. The predictor must calculate simple ETAs, compute remaining distances along routes, apply speed adjustments for conditions, and determine confidence intervals based on data quality. Includes an `ETAPredictor` class for prediction management with historical learning and a `VoyageHistoryStore` for pattern analysis.

**Key Interfaces**:
- `calculateSimpleETA(distanceNm, speedKnots)` → hours
- `calculateRemainingDistance(position, waypoints)` → nautical miles
- `adjustSpeedForConditions(baseSpeed, factors)` → adjusted knots
- `calculateConfidenceInterval(hoursRemaining, positionAge, historicalVariance)` → bounds and percent
- `ETAPredictor` with port registration, position updates, route setting, voyage recording, and condition application
- `VoyageHistoryStore` for historical data retention and statistical analysis

**Data Structures**:
- `VesselPosition` — Current position from AIS (MMSI, coordinates, speed, course, timestamp)
- `ETAPrediction` — Prediction result with estimated/earliest/latest ETA, distance, confidence level, and affecting factors
- `Waypoint` — Route waypoint with coordinates and optional name
- `CONFIDENCE_LEVEL` — Enum (high >90%, medium 70-90%, low 50-70%, uncertain <50%)
- `ETA_FACTOR` — Enum of factors affecting predictions (weather, traffic, congestion, speed_deviation, route_deviation, historical_variance)

## Getting Started
```bash
npm install
npm test
```

## Success Criteria
Implementation meets the acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md). All 3 modules must:
- Follow CommonJS patterns (`'use strict'` and `module.exports`)
- Use `Object.freeze()` for constants
- Include comprehensive unit test coverage (min 80% line coverage)
- Support integration with existing codebase modules
- Maintain error handling via return objects rather than exceptions
