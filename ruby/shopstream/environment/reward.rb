# frozen_string_literal: true

module ShopStream
  # Reward calculator for the ShopStream RL environment
  class Reward
    PASS_THRESHOLDS = [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0].freeze
    THRESHOLD_REWARDS = [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0].freeze

    REGRESSION_PENALTY = -0.15
    SECURITY_BONUS = 0.08
    DISTRIBUTED_BONUS = 0.05
    FINANCIAL_BONUS = 0.05

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
        security_tests_passing = !results[:failed_examples].any? { |e| e.match?(/security|injection|auth|IDOR/i) }
        reward += SECURITY_BONUS if security_tests_passing

        # Bonus for distributed systems tests passing
        distributed_tests_passing = !results[:failed_examples].any? { |e| e.match?(/circuit|saga|event|kafka/i) }
        reward += DISTRIBUTED_BONUS if distributed_tests_passing

        # Bonus for financial tests passing
        financial_tests_passing = !results[:failed_examples].any? { |e| e.match?(/precision|rounding|currency|refund/i) }
        reward += FINANCIAL_BONUS if financial_tests_passing
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
        'L: Setup/Configuration' => 8,
        'A: Thread Safety' => 10,
        'B: Ruby-Specific' => 10,
        'C: Callback/Lifecycle' => 8,
        'D: Database/Query' => 10,
        'E: Event Sourcing' => 8,
        'F: Distributed Systems' => 8,
        'G: Caching' => 5,
        'H: Financial/Billing' => 5,
        'I: Security' => 8,
        'J: Background Jobs' => 5
      }
    end
  end
end
