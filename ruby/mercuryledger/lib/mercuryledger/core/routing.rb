# frozen_string_literal: true

module MercuryLedger
  module Core
    module Routing
      module_function

      
      def choose_corridor(routes, blocked)
        candidates = routes.reject { |r| blocked.include?(r[:channel]) || r[:latency] < 0 }
        candidates.min_by { |r| [r[:latency], r[:channel]] }
      end

      
      def channel_score(route)
        lat = route[:latency].to_f
        rel = route.fetch(:reliability, 1.0).to_f
        return Float::INFINITY if rel <= 0

        lat / rel
      end

      
      def estimate_transit_time(distance_nm, speed_knots: 14.0)
        return 0.0 if speed_knots <= 0

        (distance_nm.to_f / speed_knots).round(2)
      end

      
      def estimate_corridor_cost(distance_nm, fuel_rate: 0.42)
        return 0.0 if distance_nm <= 0

        (distance_nm * fuel_rate).round(2)
      end

      def compare_corridors(a, b)
        score_a = channel_score(a)
        score_b = channel_score(b)
        cmp = score_a <=> score_b
        cmp.zero? ? (a[:channel] || '') <=> (b[:channel] || '') : cmp
      end

      
      def plan_multi_leg(waypoints)
        return { legs: [], total_distance: 0.0, leg_count: 0 } if waypoints.length < 2

        legs = []
        waypoints.each_cons(2) do |a, b|
          dist = ((b[:nm] || 0) - (a[:nm] || 0)).abs.to_f
          legs << { from: a[:name], to: b[:name], distance_nm: dist }
        end
        total = ((waypoints.last[:nm] || 0) - (waypoints.first[:nm] || 0)).abs.to_f
        { legs: legs, total_distance: total.round(2), leg_count: legs.length }
      end
    end

    Waypoint = Struct.new(:name, :nm, :lat, :lon, keyword_init: true)

    MultiLegPlan = Struct.new(:legs, :total_distance, keyword_init: true)

    class CorridorTable
      def initialize
        @mutex  = Mutex.new
        @routes = {}
      end

      def add(channel, route)
        @mutex.synchronize { @routes[channel] = route }
      end

      def get(channel)
        @mutex.synchronize { @routes[channel] }
      end

      def remove(channel)
        @mutex.synchronize { @routes.delete(channel) }
      end

      
      def all
        @mutex.synchronize { @routes.values.dup }
      end

      def count
        @mutex.synchronize { @routes.length }
      end

      def active
        @mutex.synchronize { @routes.values.select { |r| r[:active] == true } }
      end
    end
  end
end
