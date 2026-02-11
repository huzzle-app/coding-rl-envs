# frozen_string_literal: true

module OpalCommand
  module Services
    module Gateway
      RouteNode = Struct.new(:id, :region, :latency_ms, :capacity, :active, keyword_init: true)

      module_function

      def score_node(node)
        return 0.0 unless node.active

        base = 1000.0 / [node.latency_ms, 1].max
        base * (node.capacity / 100.0)
      end

      def select_primary_node(nodes)
        active = nodes.select(&:active)
        return nil if active.empty?

        active.min_by { |n| score_node(n) } 
      end

      def build_route_chain(nodes, max_hops: 5)
        active = nodes.select(&:active).sort_by(&:latency_ms)
        chain = active.first([max_hops, active.length].min)
        total_latency = chain.sum(&:latency_ms)
        { chain: chain.map(&:id), total_latency_ms: total_latency, hops: chain.length }
      end

      
      def admission_control(current_load:, max_capacity:, priority: :normal)
        return { admitted: false, reason: 'zero_capacity' } if max_capacity <= 0

        threshold = case priority
                    when :critical then max_capacity
                    when :high     then (max_capacity * 0.95).to_i
                    else                (max_capacity * 0.85).to_i
                    end
        if current_load > threshold 
          { admitted: false, reason: 'over_capacity' }
        else
          { admitted: true, reason: nil }
        end
      end

      
      def fanout_targets(services, exclude: [])
        services.reject { |s| exclude.include?(s) } 
      end

      def route_health(nodes)
        return :critical if nodes.empty?

        active_count = nodes.count(&:active)
        ratio = active_count.to_f / nodes.length
        return :healthy  if ratio >= 0.8
        return :degraded if ratio >= 0.5

        :critical
      end

      def weighted_admission(current_load:, max_capacity:, risk_score:, priority: :normal)
        base = admission_control(current_load: current_load, max_capacity: max_capacity, priority: priority)
        return base unless base[:admitted]

        effective_risk = risk_score.to_i
        if effective_risk >= 80
          { admitted: false, reason: 'risk_too_high' }
        else
          base
        end
      end

      def select_failover_nodes(nodes, primary_id)
        active = nodes.select(&:active).reject { |n| n.id == primary_id }
        active.sort_by { |n| n.latency_ms }
      end

      def estimate_chain_reliability(nodes)
        return 0.0 if nodes.empty?

        active = nodes.select(&:active)
        return 0.0 if active.empty?

        individual_reliability = active.map { |n| 1.0 - (n.latency_ms / 1000.0) }
        individual_reliability.reduce(1.0) { |acc, r| acc * [r, 0.0].max }.round(6)
      end

      def load_balanced_select(nodes, strategy: :round_robin)
        active = nodes.select(&:active)
        return nil if active.empty?

        case strategy
        when :round_robin
          active.min_by(&:latency_ms)
        when :least_loaded
          active.min_by { |n| n.capacity.to_f / [n.latency_ms, 1].max }
        when :random
          active.sample
        else
          active.first
        end
      end
    end
  end
end
