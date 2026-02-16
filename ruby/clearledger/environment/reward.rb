# frozen_string_literal: true

module ClearLedger
  module Reward
    module_function

    TOTAL_BUGS = 50
    TOTAL_TESTS = 1571

    PASS_THRESHOLDS = [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0].freeze
    THRESHOLD_REWARDS = [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0].freeze

    def total_bugs
      TOTAL_BUGS
    end

    def total_tests
      TOTAL_TESTS
    end

    def sparse_reward(pass_rate)
      PASS_THRESHOLDS.length.times.reverse_each do |i|
        return THRESHOLD_REWARDS[i] if pass_rate >= PASS_THRESHOLDS[i]
      end
      0.0
    end
  end
end
