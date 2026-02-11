# frozen_string_literal: true

module MercuryLedger
  module Services
    module Routing
      SERVICE = { name: 'routing', status: 'active', version: '1.0.0' }.freeze

      Leg = Struct.new(:from, :to, :distance, :risk, keyword_init: true)

      module_function

      # Compute optimal path: should sort by distance + risk, takes lowest total.
      def compute_optimal_path(legs)
        return [] if legs.nil? || legs.empty?

        
        legs.sort_by { |l| l.distance.to_f + l.risk.to_f }
      end

      # Compute channel health score from latency and reliability.
      def channel_health_score(latency, reliability)
        return 0.0 if reliability <= 0

        
        lat_score = 1.0 / (1.0 + latency.to_f)
        (lat_score * 0.3 + reliability * 0.7).round(4)
      end

      # Estimate arrival time factoring weather delay.
      def estimate_arrival_time(distance, speed, weather_factor)
        return 0.0 if distance <= 0 || speed <= 0

        base = distance.to_f / speed
        
        (base * weather_factor.to_f).round(2)
      end

      # Compute aggregate risk for a route of legs.
      def route_risk_score(legs)
        return 0.0 if legs.nil? || legs.empty?

        total_risk = legs.sum { |l| l.risk.to_f }
        
        total_risk.round(4)
      end

      
      def total_distance(legs)
        return 0.0 if legs.nil? || legs.empty?

        legs.sum { |l| l.distance.to_f }.round(2)
      end
    end
  end
end
