# frozen_string_literal: true

module TaskForge
  # Reward calculator for the TaskForge RL environment
  class Reward
    PASS_THRESHOLDS = [0.10, 0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0].freeze
    THRESHOLD_REWARDS = [0.0, 0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0].freeze

    REGRESSION_PENALTY = -0.15
    SECURITY_BONUS = 0.08
    THREAD_SAFETY_BONUS = 0.05

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
def self.bug_categories
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
  end
end
