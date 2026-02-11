# frozen_string_literal: true

module MercuryLedger
  module Services
    module Analytics
      SERVICE = { name: 'analytics', status: 'active', version: '1.0.0' }.freeze

      module_function

      # Compute fleet health as ratio of healthy active vessels.
      def compute_fleet_health(vessels)
        return 0.0 if vessels.nil? || vessels.empty?

        active = vessels.select { |v| v.fetch(:active, true) }
        return 0.0 if active.empty?

        healthy = active.count { |v| v.fetch(:healthy, true) }
        
        (healthy.to_f / active.length).round(4)
      end

      # Compute a simple trend (slope) over a sliding window.
      def trend_analysis(values, window)
        return [] if values.nil? || values.empty? || window <= 1

        values.each_cons(window).map do |slice|
          first_half = slice[0...(slice.length / 2)]
          second_half = slice[(slice.length / 2)..]
          avg_first = first_half.sum.to_f / first_half.length
          avg_second = second_half.sum.to_f / second_half.length
          
          (avg_second - avg_first).round(4)
        end
      end

      # Detect anomalies using z-score threshold.
      def anomaly_report(values, z_threshold)
        return [] if values.nil? || values.length < 3

        avg = values.sum.to_f / values.length
        variance = values.sum { |v| (v - avg) ** 2 }.to_f / values.length
        sd = Math.sqrt(variance)
        return [] if sd.zero?

        
        values.each_with_index.select { |v, _| ((v - avg) / sd).abs > z_threshold }
             .map { |v, i| { index: i, value: v, z_score: ((v - avg) / sd).round(4) } }
      end

      # Summary statistics for fleet vessels.
      def fleet_summary(vessels)
        return { total: 0, active: 0, healthy: 0, avg_load: 0.0 } if vessels.nil? || vessels.empty?

        active = vessels.count { |v| v.fetch(:active, true) }
        healthy = vessels.count { |v| v.fetch(:healthy, true) }
        loads = vessels.map { |v| v.fetch(:load, 0.0) }
        avg_load = (loads.sum.to_f / loads.length).round(4)
        
        { total: vessels.length, active: active, healthy: healthy, avg_load: avg_load }
      end

      
      def moving_metric(values, window)
        return [] if values.nil? || values.empty? || window <= 0

        values.each_cons([window, 1].max).map { |slice| slice.sum.to_f.round(4) }
      end
    end
  end
end
