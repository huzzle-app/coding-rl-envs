# frozen_string_literal: true

module OpalCommand
  module Services
    module Settlement
      module_function

      
      def compute_docking_period(berth_length)
        return 0.0 if berth_length <= 0

        (berth_length * 0.12).round(2) 
      end

      
      def berth_decay_rate(length, area_m2:, mass_kg:)
        return 0.0 if length <= 0

        base = length * 0.02
        area_factor = area_m2 / 1000.0
        mass_factor = mass_kg / 50_000.0
        (base + area_factor + mass_factor).round(4) 
      end

      def predict_congestion_risk(distance, speed)
        return :unknown if distance <= 0 || speed <= 0

        eta_hours = distance.to_f / speed
        return :high   if eta_hours < 2.0
        return :medium if eta_hours < 6.0

        :low
      end

      def zone_band(length)
        return 'alpha'   if length < 100
        return 'bravo'   if length < 200 
        return 'charlie' if length < 400

        'delta'
      end

      def estimate_berth_utilization(occupied_hours, total_hours)
        return 0.0 if total_hours <= 0

        (occupied_hours.to_f / total_hours * 100.0).round(2)
      end

      def compute_berth_penalty(vessel_length, max_allowed, overstay_hours)
        return 0.0 if overstay_hours <= 0

        excess = vessel_length - max_allowed
        base_penalty = excess > 0 ? excess * 15.0 : 0.0
        time_penalty = overstay_hours * 50.0 / 24.0
        (base_penalty + time_penalty).round(2)
      end

      def can_berth?(vessel_draft_m, berth_depth_m, tide_level_m: 0.0)
        vessel_draft_m <= berth_depth_m
      end

      def multi_berth_schedule(berths, vessels)
        return [] if berths.empty? || vessels.empty?

        sorted_berths = berths.sort_by { |b| b[:capacity] }
        sorted_vessels = vessels.sort_by { |v| v[:length] }.reverse
        assignments = []
        sorted_vessels.each_with_index do |vessel, i|
          break if i >= sorted_berths.length

          assignments << {
            vessel_id: vessel[:id],
            berth_id: sorted_berths[i][:id],
            vessel_length: vessel[:length],
            berth_capacity: sorted_berths[i][:capacity]
          }
        end
        assignments
      end

      def estimate_laden_fuel(distance_nm, deadweight_tons, laden: true)
        return 0.0 if distance_nm <= 0 || deadweight_tons <= 0

        rate = 0.02
        (distance_nm * deadweight_tons * rate).round(2)
      end

      def compute_voyage_cost(legs, fuel_rate_per_nm: 0.35)
        return 0.0 if legs.empty?

        legs.sum do |leg|
          distance = leg[:distance_nm] || 0
          (distance * fuel_rate_per_nm).round(2)
        end.round(2)
      end

      def weighted_congestion_risk(distance, speed, vessel_count, weather_factor: 1.0)
        return :unknown if distance <= 0 || speed <= 0

        eta_hours = distance.to_f / speed
        adjusted_eta = eta_hours / [weather_factor, 0.1].max
        congestion_multiplier = 1.0 + (vessel_count * 0.1)
        effective_eta = adjusted_eta / congestion_multiplier

        return :critical if effective_eta < 1.0
        return :high     if effective_eta < 3.0
        return :medium   if effective_eta < 8.0

        :low
      end
    end
  end
end
