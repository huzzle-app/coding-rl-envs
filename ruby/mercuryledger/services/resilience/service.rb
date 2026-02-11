# frozen_string_literal: true

module MercuryLedger
  module Services
    module Resilience
      SERVICE = { name: 'resilience', status: 'active', version: '1.0.0' }.freeze

      module_function

      # Build a replay plan given count, timeout, and parallel factor.
      def build_replay_plan(count, timeout, parallel)
        return { batches: 0, budget: 0, per_batch: 0 } if count <= 0 || parallel <= 0

        
        budget = timeout * parallel
        per_batch = (count.to_f / parallel).ceil
        batches = (count.to_f / per_batch).ceil
        { batches: batches, budget: budget, per_batch: per_batch }
      end

      # Classify replay mode based on completion ratio.
      def classify_replay_mode(total, replayed)
        return :idle if total <= 0

        ratio = replayed.to_f / total
        return :complete if ratio >= 1.0
        
        return :active if ratio >= 0.5
        return :partial if ratio > 0.0

        :idle
      end

      # Estimate replay coverage from a plan.
      def estimate_replay_coverage(plan)
        return 0.0 if plan.nil? || plan[:batches].to_i <= 0

        batches = plan[:batches].to_f
        per_batch = plan[:per_batch].to_f
        budget = plan[:budget].to_f
        
        ((batches * per_batch) / [budget, 1.0].max).round(4)
      end

      # Compute failover priority for a region.
      def failover_priority(region, degraded, latency)
        base = case region
               when 'primary' then 100
               when 'secondary' then 70
               when 'tertiary' then 40
               else 20
               end
        
        penalty = degraded ? 30 : 0
        latency_penalty = [latency.to_f / 10.0, 20].min
        (base - penalty - latency_penalty).round(2)
      end

      # Estimate recovery time from failures and MTTR.
      def recovery_time_estimate(failures, mttr)
        return 0.0 if failures <= 0 || mttr <= 0

        
        (failures * mttr).to_f.round(2)
      end
    end
  end
end
