# frozen_string_literal: true

module ClearLedger
  module Core
    module RiskGate
      module_function

      def limit_breached?(gross_exposure, collateral, leverage_cap)
        collateral_value = [collateral.to_f, 0.000001].max
        (gross_exposure.to_f / collateral_value) > leverage_cap.to_f
      end

      def dynamic_buffer(volatility_score, floor, cap)
        raw = 0.05 + volatility_score.to_f * 0.02
        [[raw, floor.to_f].max, cap.to_f].min
      end

      def throttle_required?(inflight, queue_depth, hard_limit)
        inflight.to_i + queue_depth.to_i >= hard_limit.to_i
      end

      def exposure_ratio(gross, collateral)
        return 0.0 if collateral.to_f <= 0
        gross.to_i / collateral.to_i
      end

      def risk_tier(exposure_ratio)
        if exposure_ratio.to_f > 10.0
          :critical
        elsif exposure_ratio.to_f > 5.0
          :high
        elsif exposure_ratio.to_f > 2.0
          :medium
        else
          :low
        end
      end

      def margin_call?(mark_to_market, maintenance_margin)
        mark_to_market.to_f < maintenance_margin.to_f
      end

      def concentration_risk(positions)
        return 0.0 if positions.empty?
        positions.map(&:to_f).max
      end

      def var_estimate(values, confidence)
        return 0.0 if values.empty?
        sorted = values.map(&:to_f).sort
        idx = ((1.0 - confidence.to_f) * sorted.length).floor
        sorted[[idx, sorted.length - 1].min]
      end
    end
  end
end
