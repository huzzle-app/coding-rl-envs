# OpalCommand - Greenfield Tasks

These tasks require implementing new modules from scratch for the OpalCommand maritime command and control platform. Each task must follow existing architectural patterns and integrate with the service ecosystem.

---

## Task 1: Berth Allocation Optimizer

### Overview

Implement a berth allocation optimization service that assigns vessels to berths based on vessel dimensions, cargo type, berth capabilities, and scheduling constraints. The optimizer must handle priority vessels, hazmat requirements, and equipment availability while minimizing turnaround time.

### Location

Create new files:
- `lib/opalcommand/core/berth_optimizer.rb`
- `services/berth_optimizer/service.rb`

### Interface Contract

```ruby
# frozen_string_literal: true

module OpalCommand
  module Core
    # Value object representing a berth with its capabilities
    # @attr_reader [String] id Unique berth identifier
    # @attr_reader [Float] length_m Maximum vessel length in meters
    # @attr_reader [Float] depth_m Water depth at berth in meters
    # @attr_reader [Integer] crane_count Number of available cranes
    # @attr_reader [Boolean] hazmat_certified Whether berth handles hazardous materials
    # @attr_reader [Array<Symbol>] equipment Available equipment types (:gantry, :mobile, :conveyor)
    Berth = Struct.new(:id, :length_m, :depth_m, :crane_count, :hazmat_certified, :equipment, keyword_init: true)

    # Value object representing a vessel requiring berth allocation
    # @attr_reader [String] id Vessel identifier
    # @attr_reader [Float] length_m Vessel length in meters
    # @attr_reader [Float] draft_m Vessel draft in meters
    # @attr_reader [Symbol] cargo_type Cargo classification (:container, :bulk, :tanker, :roro)
    # @attr_reader [Boolean] hazmat Whether carrying hazardous materials
    # @attr_reader [Integer] priority Priority level (1-5, 5 being highest)
    # @attr_reader [Time] eta Estimated time of arrival
    # @attr_reader [Integer] estimated_hours Estimated berth time in hours
    VesselRequest = Struct.new(:id, :length_m, :draft_m, :cargo_type, :hazmat, :priority, :eta, :estimated_hours, keyword_init: true)

    # Value object representing a berth assignment
    # @attr_reader [String] vessel_id Assigned vessel
    # @attr_reader [String] berth_id Assigned berth
    # @attr_reader [Time] start_time Scheduled start
    # @attr_reader [Time] end_time Scheduled end
    # @attr_reader [Float] fitness_score Assignment quality score (0.0-1.0)
    BerthAssignment = Struct.new(:vessel_id, :berth_id, :start_time, :end_time, :fitness_score, keyword_init: true)

    module BerthOptimizer
      module_function

      # Checks if a berth can physically accommodate a vessel
      # @param berth [Berth] The berth to check
      # @param vessel [VesselRequest] The vessel request
      # @return [Boolean] true if berth can accommodate vessel
      def berth_compatible?(berth, vessel)
        raise NotImplementedError
      end

      # Computes a fitness score for assigning a vessel to a berth
      # Higher scores indicate better matches
      # @param berth [Berth] The candidate berth
      # @param vessel [VesselRequest] The vessel request
      # @return [Float] Fitness score between 0.0 and 1.0
      def compute_fitness(berth, vessel)
        raise NotImplementedError
      end

      # Finds the optimal berth for a single vessel from available berths
      # @param berths [Array<Berth>] Available berths
      # @param vessel [VesselRequest] The vessel to assign
      # @return [Hash, nil] { berth: Berth, fitness: Float } or nil if no compatible berth
      def find_optimal_berth(berths, vessel)
        raise NotImplementedError
      end

      # Allocates multiple vessels to berths optimizing overall fitness
      # Respects priority ordering (higher priority vessels allocated first)
      # @param berths [Array<Berth>] Available berths
      # @param vessels [Array<VesselRequest>] Vessels to allocate
      # @return [Hash] { assignments: Array<BerthAssignment>, unassigned: Array<VesselRequest> }
      def allocate_batch(berths, vessels)
        raise NotImplementedError
      end

      # Detects scheduling conflicts between assignments
      # @param assignments [Array<BerthAssignment>] Current assignments
      # @param new_assignment [BerthAssignment] Proposed assignment
      # @return [Array<BerthAssignment>] Conflicting assignments (empty if none)
      def detect_conflicts(assignments, new_assignment)
        raise NotImplementedError
      end

      # Computes berth utilization metrics
      # @param berth_id [String] The berth to analyze
      # @param assignments [Array<BerthAssignment>] All assignments
      # @param period_hours [Integer] Analysis period in hours
      # @return [Hash] { utilization_pct: Float, idle_hours: Float, vessel_count: Integer }
      def berth_utilization(berth_id, assignments, period_hours)
        raise NotImplementedError
      end
    end

    # Thread-safe scheduler for managing berth allocations
    class BerthScheduler
      # @param berths [Array<Berth>] Available berths
      def initialize(berths)
        raise NotImplementedError
      end

      # Submits a vessel request for scheduling
      # @param request [VesselRequest] The vessel request
      # @return [BerthAssignment, nil] Assignment if successful
      def submit(request)
        raise NotImplementedError
      end

      # Cancels an existing assignment
      # @param vessel_id [String] The vessel to cancel
      # @return [Boolean] true if cancelled
      def cancel(vessel_id)
        raise NotImplementedError
      end

      # Returns all current assignments
      # @return [Array<BerthAssignment>]
      def assignments
        raise NotImplementedError
      end

      # Returns assignments for a specific time range
      # @param start_time [Time] Range start
      # @param end_time [Time] Range end
      # @return [Array<BerthAssignment>]
      def assignments_in_range(start_time, end_time)
        raise NotImplementedError
      end
    end
  end
end
```

### Required Models

1. `Berth` - Struct with berth capabilities (length, depth, cranes, hazmat certification, equipment)
2. `VesselRequest` - Struct with vessel requirements and scheduling info
3. `BerthAssignment` - Struct representing a confirmed assignment
4. `BerthScheduler` - Thread-safe class managing the assignment lifecycle

### Architectural Requirements

1. Follow the `module_function` pattern for stateless operations (see `services/settlement/service.rb`)
2. Use `Mutex` for thread-safety in stateful classes (see `Core::Dispatch::BerthPlanner`)
3. Use Struct with `keyword_init: true` for value objects (see `Services::Gateway::RouteNode`)
4. Return structured hashes for complex results (see `dispatch_batch` in `core/dispatch.rb`)

### Acceptance Criteria

1. **Unit Tests** (create `tests/unit/berth_optimizer_test.rb`):
   - `berth_compatible?` correctly validates length, draft, and hazmat requirements
   - `compute_fitness` returns scores between 0.0 and 1.0
   - `find_optimal_berth` returns highest fitness match or nil
   - `allocate_batch` respects priority ordering
   - `detect_conflicts` identifies overlapping time windows on same berth
   - `berth_utilization` computes correct percentages

2. **Service Tests** (create `tests/services/berth_optimizer_service_test.rb`):
   - `BerthScheduler` is thread-safe (concurrent submissions don't corrupt state)
   - Cancellation removes assignments and frees berth
   - `assignments_in_range` filters correctly

3. **Integration Points**:
   - Register in `shared/contracts/contracts.rb` with port 8124
   - Add `BerthOptimizer` to `SERVICE_DEFS` with dependencies on `:routing`, `:settlement`

4. **Test Command**: `bundle exec rspec` or `ruby -Ilib -Itests tests/unit/berth_optimizer_test.rb`

---

## Task 2: Cargo Manifest Validator

### Overview

Implement a cargo manifest validation service that verifies cargo declarations against international maritime regulations, weight distribution limits, and hazmat segregation rules. The validator must detect declaration anomalies, compute cargo stability metrics, and generate compliance reports.

### Location

Create new files:
- `lib/opalcommand/core/cargo_validator.rb`
- `services/cargo/service.rb`

### Interface Contract

```ruby
# frozen_string_literal: true

module OpalCommand
  module Core
    # Individual cargo item in a manifest
    # @attr_reader [String] id Unique cargo identifier
    # @attr_reader [String] description Cargo description
    # @attr_reader [Float] weight_kg Weight in kilograms
    # @attr_reader [Symbol] category Cargo category (:general, :refrigerated, :hazmat, :oversized, :liquid)
    # @attr_reader [String, nil] un_number UN hazmat number (if hazmat)
    # @attr_reader [Symbol, nil] hazmat_class IMO hazmat class (:explosive, :gas, :flammable, :oxidizer, :toxic, :radioactive, :corrosive)
    # @attr_reader [String] container_id Container identifier
    # @attr_reader [Symbol] position Stowage position (:hold, :deck, :refrigerated_hold)
    CargoItem = Struct.new(:id, :description, :weight_kg, :category, :un_number, :hazmat_class, :container_id, :position, keyword_init: true)

    # Complete vessel cargo manifest
    # @attr_reader [String] vessel_id Vessel identifier
    # @attr_reader [String] voyage_number Voyage identifier
    # @attr_reader [Array<CargoItem>] items All cargo items
    # @attr_reader [Time] declared_at Declaration timestamp
    CargoManifest = Struct.new(:vessel_id, :voyage_number, :items, :declared_at, keyword_init: true)

    # Validation result for a single rule check
    # @attr_reader [Symbol] rule Rule identifier
    # @attr_reader [Symbol] status Validation status (:pass, :warn, :fail)
    # @attr_reader [String] message Human-readable message
    # @attr_reader [Array<String>] affected_items IDs of items involved
    ValidationResult = Struct.new(:rule, :status, :message, :affected_items, keyword_init: true)

    module CargoValidator
      # IMO hazmat segregation matrix (which classes cannot be stowed together)
      HAZMAT_SEGREGATION = {
        explosive: [:gas, :flammable, :oxidizer, :toxic, :radioactive],
        gas: [:explosive, :flammable, :oxidizer],
        flammable: [:explosive, :gas, :oxidizer],
        oxidizer: [:explosive, :gas, :flammable],
        toxic: [:explosive],
        radioactive: [:explosive],
        corrosive: []
      }.freeze

      module_function

      # Validates a single cargo item for required fields and value ranges
      # @param item [CargoItem] The item to validate
      # @return [ValidationResult] Validation result
      def validate_item(item)
        raise NotImplementedError
      end

      # Validates hazmat segregation rules for all items
      # @param items [Array<CargoItem>] All cargo items
      # @return [Array<ValidationResult>] All segregation violations
      def validate_hazmat_segregation(items)
        raise NotImplementedError
      end

      # Computes weight distribution metrics
      # @param items [Array<CargoItem>] All cargo items
      # @param vessel_capacity_kg [Float] Maximum cargo capacity
      # @return [Hash] { total_kg: Float, capacity_pct: Float, hold_kg: Float, deck_kg: Float, balanced: Boolean }
      def compute_weight_distribution(items, vessel_capacity_kg)
        raise NotImplementedError
      end

      # Validates complete manifest against all rules
      # @param manifest [CargoManifest] The manifest to validate
      # @param vessel_capacity_kg [Float] Vessel cargo capacity
      # @return [Hash] { valid: Boolean, results: Array<ValidationResult>, summary: Hash }
      def validate_manifest(manifest, vessel_capacity_kg)
        raise NotImplementedError
      end

      # Detects duplicate container declarations
      # @param items [Array<CargoItem>] All cargo items
      # @return [Array<ValidationResult>] Duplicate violations
      def detect_duplicates(items)
        raise NotImplementedError
      end

      # Generates compliance report for regulatory submission
      # @param manifest [CargoManifest] Validated manifest
      # @param validation_results [Array<ValidationResult>] Validation results
      # @return [Hash] Structured compliance report
      def generate_compliance_report(manifest, validation_results)
        raise NotImplementedError
      end

      # Checks if hazmat items can be stowed together
      # @param class_a [Symbol] First hazmat class
      # @param class_b [Symbol] Second hazmat class
      # @return [Boolean] true if segregation required
      def requires_segregation?(class_a, class_b)
        raise NotImplementedError
      end
    end

    # Stateful manifest registry with versioning
    class ManifestRegistry
      def initialize
        raise NotImplementedError
      end

      # Registers a new manifest version
      # @param manifest [CargoManifest] The manifest to register
      # @return [Integer] Version number assigned
      def register(manifest)
        raise NotImplementedError
      end

      # Retrieves current manifest for a vessel
      # @param vessel_id [String] The vessel
      # @return [CargoManifest, nil]
      def current(vessel_id)
        raise NotImplementedError
      end

      # Retrieves specific version
      # @param vessel_id [String] The vessel
      # @param version [Integer] Version number
      # @return [CargoManifest, nil]
      def version(vessel_id, version)
        raise NotImplementedError
      end

      # Lists all versions for a vessel
      # @param vessel_id [String] The vessel
      # @return [Array<Integer>] Version numbers
      def versions(vessel_id)
        raise NotImplementedError
      end
    end
  end
end
```

### Required Models

1. `CargoItem` - Struct for individual cargo declarations
2. `CargoManifest` - Struct for complete vessel manifest
3. `ValidationResult` - Struct for rule check results
4. `ManifestRegistry` - Thread-safe class for manifest versioning

### Architectural Requirements

1. Define `HAZMAT_SEGREGATION` constant as a frozen hash (see `ALLOWED_ORIGINS` in `core/security.rb`)
2. Use `module_function` for validation operations
3. Return structured hashes with `:valid`, `:results` keys (see `validate_command_shape` in `services/intake/service.rb`)
4. Use `Mutex` synchronization in `ManifestRegistry` (see `TokenStore` pattern)

### Acceptance Criteria

1. **Unit Tests** (create `tests/unit/cargo_validator_test.rb`):
   - `validate_item` catches missing required fields
   - `validate_hazmat_segregation` detects incompatible hazmat classes in same position
   - `compute_weight_distribution` computes correct percentages
   - `detect_duplicates` finds containers declared multiple times
   - `requires_segregation?` correctly consults segregation matrix

2. **Service Tests** (create `tests/services/cargo_service_test.rb`):
   - `ManifestRegistry` maintains version history
   - Concurrent registration is thread-safe
   - `current` returns latest version

3. **Integration Points**:
   - Register in `shared/contracts/contracts.rb` with port 8125
   - Add to `SERVICE_DEFS` with dependencies on `:audit`, `:risk`

4. **Test Command**: `bundle exec rspec` or `ruby -Ilib -Itests tests/unit/cargo_validator_test.rb`

---

## Task 3: Vessel Tracking Service

### Overview

Implement a real-time vessel tracking service that processes AIS (Automatic Identification System) position reports, computes vessel trajectories, detects navigation anomalies, and generates proximity alerts. The service must handle high-frequency position updates efficiently and maintain historical track data.

### Location

Create new files:
- `lib/opalcommand/core/vessel_tracker.rb`
- `services/tracking/service.rb`

### Interface Contract

```ruby
# frozen_string_literal: true

module OpalCommand
  module Core
    # AIS position report from a vessel
    # @attr_reader [String] mmsi Maritime Mobile Service Identity
    # @attr_reader [Float] latitude Decimal degrees (-90 to 90)
    # @attr_reader [Float] longitude Decimal degrees (-180 to 180)
    # @attr_reader [Float] speed_knots Speed over ground
    # @attr_reader [Float] course_deg Course over ground (0-360)
    # @attr_reader [Float] heading_deg True heading (0-360)
    # @attr_reader [Time] timestamp Position timestamp
    # @attr_reader [Symbol] nav_status Navigation status (:underway, :anchored, :moored, :restricted, :not_under_command)
    PositionReport = Struct.new(:mmsi, :latitude, :longitude, :speed_knots, :course_deg, :heading_deg, :timestamp, :nav_status, keyword_init: true)

    # Computed vessel track segment
    # @attr_reader [String] mmsi Vessel identifier
    # @attr_reader [Array<PositionReport>] positions Ordered positions
    # @attr_reader [Float] total_distance_nm Total distance in nautical miles
    # @attr_reader [Float] avg_speed_knots Average speed
    # @attr_reader [Time] start_time Track start
    # @attr_reader [Time] end_time Track end
    TrackSegment = Struct.new(:mmsi, :positions, :total_distance_nm, :avg_speed_knots, :start_time, :end_time, keyword_init: true)

    # Navigation anomaly detection result
    # @attr_reader [String] mmsi Affected vessel
    # @attr_reader [Symbol] anomaly_type Type (:speed_anomaly, :course_deviation, :position_jump, :ais_gap)
    # @attr_reader [String] description Human-readable description
    # @attr_reader [Time] detected_at Detection timestamp
    # @attr_reader [Hash] details Additional context
    NavigationAnomaly = Struct.new(:mmsi, :anomaly_type, :description, :detected_at, :details, keyword_init: true)

    # Proximity alert between vessels
    # @attr_reader [String] mmsi_a First vessel
    # @attr_reader [String] mmsi_b Second vessel
    # @attr_reader [Float] distance_nm Distance between vessels
    # @attr_reader [Float] cpa_nm Closest point of approach
    # @attr_reader [Float] tcpa_minutes Time to CPA in minutes
    # @attr_reader [Symbol] severity Alert severity (:info, :warning, :danger)
    ProximityAlert = Struct.new(:mmsi_a, :mmsi_b, :distance_nm, :cpa_nm, :tcpa_minutes, :severity, keyword_init: true)

    module VesselTracker
      # Earth radius in nautical miles for distance calculations
      EARTH_RADIUS_NM = 3440.065

      module_function

      # Computes great-circle distance between two positions
      # @param lat1 [Float] First latitude
      # @param lon1 [Float] First longitude
      # @param lat2 [Float] Second latitude
      # @param lon2 [Float] Second longitude
      # @return [Float] Distance in nautical miles
      def haversine_distance(lat1, lon1, lat2, lon2)
        raise NotImplementedError
      end

      # Validates a position report for valid coordinates and values
      # @param report [PositionReport] The report to validate
      # @return [Hash] { valid: Boolean, errors: Array<String> }
      def validate_position(report)
        raise NotImplementedError
      end

      # Computes a track segment from position reports
      # @param reports [Array<PositionReport>] Chronological position reports
      # @return [TrackSegment] Computed track segment
      def compute_track(reports)
        raise NotImplementedError
      end

      # Detects anomalies comparing consecutive position reports
      # @param previous [PositionReport] Previous position
      # @param current [PositionReport] Current position
      # @param max_speed_knots [Float] Maximum expected speed
      # @param max_gap_minutes [Float] Maximum expected gap between reports
      # @return [Array<NavigationAnomaly>] Detected anomalies
      def detect_anomalies(previous, current, max_speed_knots: 30.0, max_gap_minutes: 15.0)
        raise NotImplementedError
      end

      # Computes closest point of approach between two vessels
      # @param vessel_a [PositionReport] First vessel position
      # @param vessel_b [PositionReport] Second vessel position
      # @return [Hash] { cpa_nm: Float, tcpa_minutes: Float, current_distance_nm: Float }
      def compute_cpa(vessel_a, vessel_b)
        raise NotImplementedError
      end

      # Generates proximity alerts for vessels within range
      # @param positions [Array<PositionReport>] Current positions of all vessels
      # @param danger_nm [Float] Danger threshold in nautical miles
      # @param warning_nm [Float] Warning threshold in nautical miles
      # @return [Array<ProximityAlert>] Generated alerts
      def check_proximity(positions, danger_nm: 0.5, warning_nm: 2.0)
        raise NotImplementedError
      end

      # Interpolates position at a given time between two reports
      # @param report_a [PositionReport] Earlier position
      # @param report_b [PositionReport] Later position
      # @param target_time [Time] Time to interpolate
      # @return [Hash] { latitude: Float, longitude: Float, interpolated: Boolean }
      def interpolate_position(report_a, report_b, target_time)
        raise NotImplementedError
      end

      # Computes estimated time of arrival at destination
      # @param current [PositionReport] Current position
      # @param dest_lat [Float] Destination latitude
      # @param dest_lon [Float] Destination longitude
      # @return [Hash] { eta: Time, distance_nm: Float, hours_remaining: Float }
      def estimate_eta(current, dest_lat, dest_lon)
        raise NotImplementedError
      end
    end

    # Thread-safe vessel position store with automatic track building
    class PositionStore
      # @param max_history [Integer] Maximum positions to retain per vessel
      def initialize(max_history: 1000)
        raise NotImplementedError
      end

      # Records a new position report
      # @param report [PositionReport] The position report
      # @return [Array<NavigationAnomaly>] Any anomalies detected
      def record(report)
        raise NotImplementedError
      end

      # Gets latest position for a vessel
      # @param mmsi [String] The vessel MMSI
      # @return [PositionReport, nil]
      def latest(mmsi)
        raise NotImplementedError
      end

      # Gets track for a vessel within time range
      # @param mmsi [String] The vessel MMSI
      # @param start_time [Time] Range start
      # @param end_time [Time] Range end
      # @return [TrackSegment]
      def track(mmsi, start_time, end_time)
        raise NotImplementedError
      end

      # Gets all vessels with positions newer than threshold
      # @param since [Time] Minimum timestamp
      # @return [Array<String>] Active vessel MMSIs
      def active_vessels(since)
        raise NotImplementedError
      end

      # Returns current positions for all active vessels
      # @return [Array<PositionReport>]
      def all_current_positions
        raise NotImplementedError
      end

      # Clears old positions beyond retention window
      # @param older_than [Time] Cutoff time
      # @return [Integer] Number of positions removed
      def cleanup(older_than)
        raise NotImplementedError
      end
    end
  end
end
```

### Required Models

1. `PositionReport` - Struct for AIS position data
2. `TrackSegment` - Struct for computed vessel tracks
3. `NavigationAnomaly` - Struct for detected anomalies
4. `ProximityAlert` - Struct for collision risk alerts
5. `PositionStore` - Thread-safe class for position history

### Architectural Requirements

1. Define `EARTH_RADIUS_NM` as a constant for distance calculations
2. Use `module_function` for stateless tracking operations
3. Implement haversine formula for great-circle distance
4. Use `Mutex` in `PositionStore` for thread-safety
5. Return structured hashes for complex computations (see `compute_fleet_health` pattern)

### Acceptance Criteria

1. **Unit Tests** (create `tests/unit/vessel_tracker_test.rb`):
   - `haversine_distance` computes correct distances (test known coordinates)
   - `validate_position` catches invalid lat/lon ranges
   - `compute_track` calculates correct total distance and average speed
   - `detect_anomalies` identifies speed violations and position jumps
   - `compute_cpa` returns correct CPA and TCPA values
   - `check_proximity` generates alerts at correct thresholds
   - `interpolate_position` returns correct intermediate positions

2. **Service Tests** (create `tests/services/tracking_service_test.rb`):
   - `PositionStore` maintains correct history limit
   - `record` returns anomalies detected during recording
   - `track` returns positions within specified time range
   - `cleanup` removes positions older than threshold
   - Thread-safety under concurrent access

3. **Integration Points**:
   - Register in `shared/contracts/contracts.rb` with port 8126
   - Add to `SERVICE_DEFS` with dependencies on `:gateway`, `:notifications`

4. **Test Command**: `bundle exec rspec` or `ruby -Ilib -Itests tests/unit/vessel_tracker_test.rb`

---

## General Guidelines

### Code Style

1. All files must begin with `# frozen_string_literal: true`
2. Use 2-space indentation
3. Add YARD documentation for all public methods
4. Follow existing naming conventions (snake_case for methods, CamelCase for classes)

### Testing Standards

1. Each module function needs at least 2 test cases (happy path + edge case)
2. Test boundary conditions explicitly
3. Thread-safety tests should use multiple threads with shared state
4. Use `assert_in_delta` for floating-point comparisons

### Integration Checklist

For each new service:
- [ ] Core module in `lib/opalcommand/core/`
- [ ] Service wrapper in `services/<name>/service.rb`
- [ ] Contract registration in `shared/contracts/contracts.rb`
- [ ] Unit tests in `tests/unit/`
- [ ] Service tests in `tests/services/`
- [ ] Require added to `lib/opalcommand.rb`
