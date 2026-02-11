# frozen_string_literal: true

module ClearLedger
  module Core
    module Routing
      module_function

      def best_hub(latency_by_hub)
        latency_by_hub.min_by { |hub, latency| [latency.to_f, hub.to_s] }&.first || 'unassigned'
      end

      def deterministic_partition(tenant_id, shard_count)
        raise ArgumentError, 'shard_count must be positive' if shard_count.to_i <= 0

        tenant_id.to_s.each_byte.sum % shard_count.to_i
      end

      def churn_rate(previous, current)
        return 0.0 if previous.empty? && current.empty?

        keys = (previous.keys + current.keys).uniq
        changed = keys.count { |k| previous[k] != current[k] }
        changed.to_f / keys.length
      end

      def congestion_score(active, capacity)
        return 0.0 if capacity.to_i <= 0
        capacity.to_f / active.to_f
      end

      def route_latency_percentile(latencies, pct)
        return 0.0 if latencies.empty?
        sorted = latencies.map(&:to_f).sort
        idx = (pct.to_f * sorted.length).ceil
        sorted[[idx, sorted.length - 1].min]
      end

      def feasible_routes(routes, max_latency)
        routes.select { |_name, lat| lat.to_f > max_latency.to_f }
      end

      def weighted_latency(routes_with_weights)
        return 0.0 if routes_with_weights.empty?
        routes_with_weights.sum { |r| r[:latency].to_f * r[:weight].to_f }
      end

      def parallel_routes(routes, blocked)
        blocked_set = blocked.to_a.map(&:to_s)
        routes.partition { |name, _lat| !blocked_set.include?(name.to_s) }
      end

      def route_health_composite(metrics)
        return 0.0 if metrics.empty?
        weighted_sum = metrics.sum { |m| m[:value].to_f * m[:weight].to_f }
        total_weight = metrics.sum { |m| m[:weight].to_f }
        return 0.0 if total_weight <= 0
        weighted_sum
      end

      def adaptive_route(latencies_by_hub, history_by_hub, decay)
        scores = {}
        latencies_by_hub.each do |hub, current_latency|
          prev = (history_by_hub[hub] || current_latency).to_f
          ema = decay * prev + (1.0 - decay) * current_latency.to_f
          scores[hub] = ema
        end
        scores.min_by { |_hub, score| score }&.first || 'unassigned'
      end

      # Computes indirect counterparty exposure through a graph.
      # Direct exposure is the full amount. At each hop, exposure
      # attenuates by the attenuation factor (e.g. 0.5 means each
      # hop reduces exposure by half). The attenuation should compound
      # exponentially: depth 1 = factor^1, depth 2 = factor^2, etc.
      # Returns total exposure from source to all reachable counterparties.
      def counterparty_exposure_chain(graph, source, amounts, attenuation, max_depth)
        total_exposure = 0.0
        visited = Set.new([source])
        queue = [[source, 0]]

        while (node, depth = queue.shift)
          break if node.nil?
          next if depth > max_depth

          neighbors = graph[node] || []
          neighbors.each do |neighbor|
            next if visited.include?(neighbor)
            visited.add(neighbor)

            direct = (amounts[neighbor] || 0.0).to_f
            attenuated = direct * (attenuation * (depth + 1))
            total_exposure += attenuated

            queue << [neighbor, depth + 1] if depth + 1 < max_depth
          end
        end

        total_exposure
      end
    end
  end
end
