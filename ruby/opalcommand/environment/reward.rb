# frozen_string_literal: true

module OpalCommand
  module Reward
    module_function

    TOTAL_BUGS = 1240
    TOTAL_TESTS = 10_855

    PASS_THRESHOLDS = [0.10, 0.22, 0.36, 0.52, 0.67, 0.80, 0.90, 0.96, 0.99, 1.0].freeze
    THRESHOLD_REWARDS = [0.0, 0.015, 0.05, 0.11, 0.19, 0.31, 0.47, 0.66, 0.85, 1.0].freeze

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
