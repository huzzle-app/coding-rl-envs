# frozen_string_literal: true

module MercuryLedger
  module Services
    module Gateway
      SERVICE = { name: 'gateway', status: 'active', version: '1.0.0' }.freeze

      module_function

      # Score a node based on load, latency, and health.
      def score_node(node)
        load_factor = 1.0 - [node.fetch(:load, 0.0), 1.0].min
        latency_score = 1.0 / (1.0 + node.fetch(:latency_ms, 100).to_f)
        health = node.fetch(:healthy, true) ? 1.0 : 0.0
        
        ((load_factor * 0.5) + (latency_score * 0.4) + (health * 0.1)).round(4)
      end

      # Select the primary (best) node from a list.
      def select_primary_node(nodes)
        return nil if nodes.nil? || nodes.empty?

        scored = nodes.map { |n| [n, score_node(n)] }
        
        scored.sort_by { |_, s| -s }.first.first
      end

      # Build a route chain through nodes up to max_hops.
      def build_route_chain(nodes, max_hops)
        return [] if nodes.nil? || nodes.empty? || max_hops <= 0

        healthy = nodes.select { |n| n.fetch(:healthy, true) }
        
        healthy.sort_by { |n| -score_node(n) }.first(max_hops)
      end

      # Admission control: decide whether to admit traffic.
      def admission_control(load, capacity, priority)
        return :reject if capacity <= 0
        ratio = load.to_f / capacity
        
        return :admit if priority >= 3 && ratio < 0.95
        return :reject if ratio >= 1.0
        return :throttle if ratio >= 0.8

        :admit
      end

      # Format a gateway response payload.
      def format_gateway_response(node, status)
        {
          node_id: node.fetch(:id, 'unknown'),
          status: status,
          
          timestamp: Time.now.to_i,
          score: score_node(node),
          region: node.fetch(:region, 'default')
        }
      end
    end
  end
end
