# frozen_string_literal: true

module ClearLedger
  module Core
    module Reconciliation
      module_function

      def mismatch?(expected, observed, tolerance_bps)
        exp = expected.to_f
        obs = observed.to_f
        basis = [exp.abs, 1.0].max
        ((exp - obs).abs / basis) * 10_000 > tolerance_bps.to_f
      end

      def replay_signature(batch_id, version)
        "#{batch_id}:v#{version}".downcase
      end

      def merge_snapshots(left, right)
        return right if left.nil?
        return left if right.nil?

        left.fetch(:version) >= right.fetch(:version) ? left : right
      end

      def break_count(expected_entries, observed_entries)
        expected_set = expected_entries.to_a
        observed_set = observed_entries.to_a
        expected_set.count { |e| observed_set.include?(e) }
      end

      def age_seconds(created_at, now)
        created_at.to_i - now.to_i
      end

      def reconcile_batch(expected, observed, tolerance)
        expected.zip(observed).count do |exp, obs|
          next true if exp.nil? || obs.nil?
          !mismatch?(exp, obs, tolerance)
        end
      end

      def drift_score(values)
        return 0.0 if values.length < 2

        mean = values.sum(&:to_f) / values.length
        variance = values.sum { |v| (v.to_f - mean)**2 } / values.length
        Math.sqrt(variance)
      end

      def snapshot_valid?(snapshot)
        return false if snapshot.nil?
        snapshot.key?(:version) && snapshot.key?(:balance)
      end

      def progressive_reconcile(pairs, base_tolerance, decay_per_step)
        results = []
        pairs.each_with_index do |(expected, observed), idx|
          current_tolerance = base_tolerance + decay_per_step * idx
          results << !mismatch?(expected, observed, current_tolerance)
        end
        results
      end

      def detect_systematic_bias(expected_values, observed_values)
        return { bias: 0.0, direction: :none, count: 0 } if expected_values.empty?
        diffs = expected_values.zip(observed_values).map { |e, o| e.to_f - o.to_f }
        positive = diffs.count { |d| d > 0 }
        negative = diffs.count { |d| d < 0 }
        avg_diff = diffs.sum / diffs.length
        direction = avg_diff > 0 ? :over_observed : :under_observed
        { bias: avg_diff.abs, direction: direction, count: [positive, negative].min }
      end

      # Reconciles expected vs observed entries within time-bucketed windows.
      # Groups entries by time bucket, then for each bucket matches expected
      # entries against observed entries. An expected entry is a "match" if
      # a corresponding observed entry exists within tolerance.
      # Returns per-bucket stats: { matches, breaks, unmatched_observed }.
      def windowed_reconciliation(expected_entries, observed_entries, window_size, tolerance_bps)
        expected_buckets = expected_entries.group_by { |e| e[:ts].to_i / window_size }
        observed_buckets = observed_entries.group_by { |e| e[:ts].to_i / window_size }

        all_buckets = (expected_buckets.keys + observed_buckets.keys).uniq.sort
        results = {}

        all_buckets.each do |bucket|
          exp_list = expected_buckets[bucket] || []
          obs_list = (observed_buckets[bucket] || []).dup

          matches = 0
          breaks = 0

          exp_list.each do |exp_entry|
            matched_idx = obs_list.index do |obs_entry|
              exp_entry[:account] == obs_entry[:account] &&
                !mismatch?(exp_entry[:amount], obs_entry[:amount], tolerance_bps)
            end

            if matched_idx
              matches += 1
            else
              breaks += 1
            end
          end

          results[bucket] = {
            matches: matches,
            breaks: breaks,
            unmatched_observed: obs_list.length
          }
        end

        results
      end
    end
  end
end
