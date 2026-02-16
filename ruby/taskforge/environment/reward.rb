# frozen_string_literal: true

module TaskForge
  # Reward calculator for the TaskForge RL environment
  class Reward
    PASS_THRESHOLDS = [0.50, 0.75, 0.90, 1.0].freeze
    THRESHOLD_REWARDS = [0.15, 0.35, 0.65, 1.0].freeze

    REGRESSION_PENALTY = -0.15
    SECURITY_BONUS = 0.08
    THREAD_SAFETY_BONUS = 0.05

    # Bug categories with counts
    BUG_CATEGORIES = {
      'setup' => %w[L1 L2 L3 L4 L5],
      'thread_safety' => %w[A1 A2 A3 A4 A5 A6 A7 A8 A9 A10 A11],
      'ruby_specific' => %w[B1 B2 B3 B4 B5 B6 B7 B8 B9],
      'callback' => %w[C1 C2 C3 C4 C5 C6 C7 C8 C9],
      'database' => %w[D1 D2 D3 D4 D5 D6 D7 D8 D9 D10 D11 D12 D13 D14],
      'schema' => %w[E1 E2 E3 E4 E5 E6 E7 E8],
      'calculation' => %w[F1 F2],
      'security' => %w[I1 I2 I3 I4 I5 I6 I7 I8 I9 I10 I11 I12],
      'jobs' => %w[J1 J2 J3 J4 J5]
    }.freeze

    # Map bug IDs to test keywords for progress tracking
    BUG_TEST_MAPPING = {
      'L3' => %w[active_job queue_adapter],
      'L4' => %w[session_store api_only],
      'B2' => %w[preferences theme string symbol key],
      'A1' => %w[thread-safe profile concurrent],
      'D1' => %w[N\\+1 as_json serialize],
      'C1' => %w[deactivate notification failure gracefully],
      'A4' => %w[position concurrent unique],
      'D4' => %w[dependencies N\\+1 assignee],
      'B5' => %w[add_tag mutable default accumulate],
      'C4' => %w[assign_to notification save],
      'A5' => %w[debounce stats callback],
      'D3' => %w[completion_percentage single query],
      'A3' => %w[stats thread concurrent],
      'A2' => %w[increment atomic concurrent],
      'D2' => %w[member_details N\\+1],
      'I3' => %w[SQL injection parameterized],
      'C2' => %w[sync callback infinite loop],
      'D6' => %w[raises error nil validation],
      'I2' => %w[authorization development bypass],
      'B8' => %w[duplicate independent copy shallow],
      'B7' => %w[default_options share instance],
      'A8' => %w[singleton concurrent thread],
      'D8' => %w[cache unbounded limit],
      'C7' => %w[push notification failure gracefully],
      'I4' => %w[user search organization scope],
      'I7' => %w[timing attack generic error],
      'I8' => %w[enumeration error message],
      'C9' => %w[email asynchronously deliver_later],
      'I12' => %w[token blacklist invalidate logout],
      'D7' => %w[bulk assign update individual],
      'E4' => %w[move_to_project transaction rollback atomic]
    }.freeze

    # Bug dependencies — prerequisite bugs that must be fixed first
    BUG_DEPENDENCIES = {
      'A4' => ['L3'],         # Position race needs ActiveJob for test env
      'D1' => ['L3'],         # N+1 tests need jobs configured
      'D2' => ['L3'],
      'A5' => ['L3'],         # Debouncing needs job adapter
      'C4' => ['B5'],         # Notification ordering needs correct defaults
      'I3' => ['B2'],         # SQL injection fix often found after string/symbol awareness
      'I12' => ['I7', 'I8'],  # Token blacklist depends on consistent auth errors
      'E4' => ['D6'],         # Transaction wrapping needed after error handling fix
      'B8' => ['B7'],         # Shallow copy fix after shared options fix
      'C7' => ['A8'],         # Push notification error handling after singleton fix
      'D7' => ['I2'],         # Bulk assign auth after dev bypass fix
      'A2' => ['L3'],         # Concurrent increment needs proper job adapter
      'D3' => ['L3'],         # Single query completion needs proper env
      'C2' => ['L3']          # Callback loop detection needs job adapter
    }.freeze

    def initialize
      @previous_pass_rate = 0.0
    end

    def calculate(results, previous_pass_rate = nil)
      @previous_pass_rate = previous_pass_rate if previous_pass_rate

      return 0.0 if results[:total].zero?

      pass_rate = results[:passed].to_f / results[:total]

      # Base reward from threshold
      reward = sparse_reward(pass_rate)

      # Regression penalty
      if pass_rate < @previous_pass_rate
        reward += REGRESSION_PENALTY * (@previous_pass_rate - pass_rate)
      end

      # Bonus for security-related tests passing
      if results[:failed_examples]
        security_tests_passing = !results[:failed_examples].any? { |e| e.match?(/security|injection|auth/i) }
        reward += SECURITY_BONUS if security_tests_passing

        # Bonus for thread safety tests passing
        thread_tests_passing = !results[:failed_examples].any? { |e| e.match?(/thread|race|concurrent|singleton/i) }
        reward += THREAD_SAFETY_BONUS if thread_tests_passing
      end

      @previous_pass_rate = pass_rate

      # Clamp to [0, 1]
      [[reward, 0.0].max, 1.0].min
    end

    def sparse_reward(pass_rate)
      PASS_THRESHOLDS.reverse.each_with_index do |threshold, idx|
        return THRESHOLD_REWARDS[THRESHOLD_REWARDS.size - 1 - idx] if pass_rate >= threshold
      end
      0.0
    end

    # Track per-bug progress based on test results
    def bug_progress(results)
      return {} unless results[:failed_examples]

      progress = {}
      BUG_TEST_MAPPING.each do |bug_id, keywords|
        # Bug is fixed if no failed tests match its keywords
        matching_failures = results[:failed_examples].select do |desc|
          keywords.any? { |kw| desc.match?(/#{kw}/i) }
        end
        progress[bug_id] = matching_failures.empty? ? 1.0 : 0.0
      end
      progress
    end

    # Class methods for dependency analysis
    class << self
      def max_dependency_depth
        depths = {}
        BUG_DEPENDENCIES.each_key do |bug_id|
          depths[bug_id] = compute_depth(bug_id, Set.new)
        end
        depths.values.max || 0
      end

      def diamond_bugs
        # Bugs that are depended on by multiple other bugs
        dep_counts = Hash.new(0)
        BUG_DEPENDENCIES.each_value do |deps|
          deps.each { |d| dep_counts[d] += 1 }
        end
        dep_counts.select { |_, count| count > 1 }.keys
      end

      def cross_category_deps
        cross = []
        BUG_DEPENDENCIES.each do |bug_id, deps|
          bug_cat = category_for(bug_id)
          deps.each do |dep|
            dep_cat = category_for(dep)
            cross << [bug_id, dep] if bug_cat != dep_cat
          end
        end
        cross
      end

      def dependency_coverage
        all_bugs = BUG_CATEGORIES.values.flatten
        bugs_with_deps = BUG_DEPENDENCIES.keys
        ((bugs_with_deps.size.to_f / all_bugs.size) * 100).round(1)
      end

      def bug_categories
        {
          'L: Setup/Configuration' => 5,
          'A: Thread Safety' => 11,
          'B: Ruby-Specific' => 9,
          'C: Callback/Lifecycle' => 9,
          'D: Database/Query' => 14,
          'E: Missing Index' => 8,
          'F: Calculation' => 2,
          'I: Security' => 12,
          'J: Background Jobs' => 5
        }
      end

      private

      def compute_depth(bug_id, visited)
        return 0 if visited.include?(bug_id)

        visited.add(bug_id)
        deps = BUG_DEPENDENCIES[bug_id] || []
        return 0 if deps.empty?

        1 + deps.map { |d| compute_depth(d, visited.dup) }.max
      end

      def category_for(bug_id)
        prefix = bug_id.gsub(/\d+/, '')
        BUG_CATEGORIES.each do |_name, bugs|
          return _name if bugs.any? { |b| b.start_with?(prefix) }
        end
        'unknown'
      end
    end
  end
end
