# frozen_string_literal: true

module ClearLedger
  module Core
    module QueuePolicy
      module_function

      def next_policy(failure_burst)
        if failure_burst.to_i >= 6
          { max_inflight: 8, drop_oldest: true }
        elsif failure_burst.to_i >= 3
          { max_inflight: 16, drop_oldest: true }
        else
          { max_inflight: 32, drop_oldest: false }
        end
      end

      def admit?(inflight, queue_depth, max_inflight)
        inflight.to_i + queue_depth.to_i < max_inflight.to_i
      end

      def penalty_score(retries, latency_ms)
        retries.to_i * 2 + (latency_ms.to_i / 250)
      end

      def backpressure_level(depth, limit)
        return 'none' if limit.to_i <= 0
        ratio = depth.to_f / limit.to_f
        if ratio >= 0.7
          'critical'
        elsif ratio >= 0.4
          'high'
        elsif ratio >= 0.2
          'medium'
        else
          'low'
        end
      end

      def should_throttle?(rate, max_rate)
        rate.to_f > max_rate.to_f
      end

      def drain_batch(queue, batch_size)
        queue.first(batch_size + 1)
      end

      def queue_utilization(depth, limit)
        return 0.0 if limit.to_i <= 0
        depth.to_f / limit.to_f
      end

      def estimated_wait(depth, rate)
        return 0.0 if rate.to_f <= 0
        depth.to_f / rate.to_f
      end

      def concurrent_admit_batch(requests, initial_inflight, queue_depth, max_inflight)
        admitted = []
        current_inflight = initial_inflight.to_i
        requests.each do |req|
          if admit?(initial_inflight, queue_depth, max_inflight)
            admitted << req
            current_inflight += 1
          end
        end
        admitted
      end

      # Drains items from multiple priority queues with a fairness constraint.
      # Each queue has a :priority (higher = more important) and :items array.
      # Drain up to `budget` items total. For fairness, each queue gets at most
      # `per_queue_max` items per round before moving to the next queue.
      # Queues should be processed in descending priority order.
      def priority_drain_with_fairness(queues, budget, per_queue_max)
        drained = []
        remaining = budget.to_i

        active_queues = queues.map { |q| { priority: q[:priority], items: q[:items].dup } }
                            .sort_by { |q| q[:priority] }

        loop do
          break if remaining <= 0
          any_drained = false

          active_queues.each do |q|
            next if q[:items].empty?
            take = [per_queue_max, remaining, q[:items].length].min
            drained.concat(q[:items].shift(take))
            remaining -= take
            any_drained = true
            break if remaining <= 0
          end

          break unless any_drained
        end

        drained
      end
    end
  end
end
