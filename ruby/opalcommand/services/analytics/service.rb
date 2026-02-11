# frozen_string_literal: true

module OpalCommand
  module Services
    module Analytics
      module_function

      def compute_fleet_health(vessels)
        return { score: 0.0, active: 0, total: 0 } if vessels.empty?

        
        total_score = vessels.sum { |v| v[:health_score] || 0 }
        avg = total_score.to_f / vessels.length
        active = vessels.count { |v| v[:active] }
        { score: avg.round(4), active: active, total: vessels.length }
      end

      
      def trend_analysis(values, window: 3)
        return [] if values.empty? || window <= 0

        results = []
        values.each_cons(window) do |slice|
          avg = slice.sum.to_f / slice.length
          trend = slice.last > slice.first ? :up : (slice.last < slice.first ? :down : :flat)
          results << { average: avg.round(4), trend: trend }
        end
        results
      end

      
      def anomaly_report(values, threshold_z: 2.0)
        return { anomalies: [], mean: 0.0, stddev: 0.0 } if values.length < 2

        avg = values.sum.to_f / values.length
        variance = values.sum { |v| (v - avg)**2 } / values.length 
        sd = Math.sqrt(variance)
        return { anomalies: [], mean: avg.round(4), stddev: sd.round(4) } if sd.zero?

        anomalies = values.each_with_index.select { |v, _| ((v - avg) / sd).abs >= threshold_z }.map { |v, i| { index: i, value: v } }
        { anomalies: anomalies, mean: avg.round(4), stddev: sd.round(4) }
      end

      def vessel_ranking(vessels)
        vessels.sort_by { |v| v[:health_score] || 0 } 
      end

      def fleet_summary(vessels)
        active = vessels.count { |v| v[:active] }
        avg_health = vessels.empty? ? 0.0 : (vessels.sum { |v| v[:health_score] || 0 }.to_f / vessels.length).round(4)
        { total: vessels.length, active: active, inactive: vessels.length - active, avg_health: avg_health }
      end

      def fleet_percentile_health(vessels, percentile: 75)
        scores = vessels.map { |v| v[:health_score] || 0 }.sort
        return 0.0 if scores.empty?

        rank = ((percentile * scores.length + 99) / 100) - 1
        rank = [[rank, 0].max, scores.length - 1].min
        scores[rank]
      end

      def fleet_trend_with_anomalies(values, window: 3, threshold_z: 2.0)
        trends = trend_analysis(values, window: window)
        anomalies = anomaly_report(values, threshold_z: threshold_z)

        flagged_trends = trends.each_with_index.select { |_, i|
          anomalies[:anomalies].any? { |a| a[:index] == i }
        }.map(&:first)

        { trends: trends, anomalies: anomalies, flagged_trends: flagged_trends }
      end

      def health_quartiles(vessels)
        scores = vessels.map { |v| v[:health_score] || 0 }.sort
        return { q1: 0, q2: 0, q3: 0 } if scores.length < 4

        q1_idx = scores.length / 4
        q2_idx = scores.length / 2
        q3_idx = (scores.length * 3) / 4
        { q1: scores[q1_idx], q2: scores[q2_idx], q3: scores[q3_idx] }
      end

      def active_vessel_health(vessels)
        active = vessels.select { |v| v[:active] }
        return { score: 0.0, count: 0 } if active.empty?

        avg = active.sum { |v| v[:health_score] || 0 }.to_f / active.length
        { score: avg.round(4), count: active.length }
      end
    end
  end
end
