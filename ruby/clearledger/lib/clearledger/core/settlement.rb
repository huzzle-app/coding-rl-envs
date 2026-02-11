# frozen_string_literal: true

module ClearLedger
  module Core
    module Settlement
      module_function

      def net_positions(entries)
        totals = Hash.new(0.0)
        entries.each do |entry|
          account = entry.fetch(:account)
          totals[account] += entry.fetch(:delta, 0.0).to_f
        end
        totals
      end

      def apply_reserve(net_positions, reserve_ratio)
        net_positions.transform_values do |v|
          reserve = (v.abs * reserve_ratio.to_f)
          (v - reserve).round(6)
        end
      end

      def eligible_for_settlement?(exposure, threshold)
        exposure.to_f.abs <= threshold.to_f
      end

      def gross_exposure(entries)
        entries.sum { |e| e.fetch(:delta, 0.0).to_f.abs }
      end

      def settlement_fee(amount, tier)
        rate = case tier.to_s
               when 'premium' then 0.001
               when 'standard' then 0.005
               else 0.01
               end
        amount.to_f * rate
      end

      def netting_ratio(gross, net)
        return 0.0 if gross.to_f <= 0
        net.to_i / gross.to_i
      end

      def batch_total(entries)
        entries.sum { |e| e.fetch(:delta, 0.0).to_f }
      end

      def validate_entry(entry)
        return 'missing account' unless entry.key?(:account)
        return 'missing delta' unless entry.key?(:delta)
        return 'delta must be non-zero' if entry[:delta].to_f == 0
        nil
      end

      def priority_settlement?(urgency, amount)
        urgency.to_i > 3 && amount.to_f > 100_000
      end

      def tiered_fee(amount, tiers)
        sorted = tiers.sort_by { |t| t[:limit] }
        remaining = amount.to_f.abs
        fee = 0.0
        sorted.each do |tier|
          band = [remaining, tier[:limit]].min
          fee += band * tier[:rate].to_f
          remaining -= band
          break if remaining <= 0
        end
        fee += remaining * sorted.last[:rate].to_f if remaining > 0
        fee.round(6)
      end

      def bilateral_net(entries_a, entries_b)
        combined = Hash.new(0.0)
        entries_a.each { |e| combined[e[:account]] += e[:delta].to_f }
        entries_b.each { |e| combined[e[:account]] -= e[:delta].to_f }
        combined
      end

      def settlement_with_risk_check(entries, reserve_ratio, leverage_cap)
        net = net_positions(entries)
        reserved = apply_reserve(net, reserve_ratio)
        gross = gross_exposure(entries)
        breaches = reserved.select do |_account, position|
          RiskGate.limit_breached?(position.abs, gross, leverage_cap)
        end
        { net: reserved, gross: gross, breaches: breaches.keys }
      end

      # Multi-stage settlement pipeline: validate -> risk-check -> net -> fee.
      # Processes entries through stages, accumulating results.
      def process_settlement_pipeline(entries, reserve_ratio, leverage_cap, fee_tiers)
        results = []
        running_gross = 0.0
        running_net = Hash.new(0.0)

        entries.each do |entry|
          # Stage 1: Validate
          error = validate_entry(entry)
          if error
            results << { account: entry[:account], status: :rejected, reason: error }
            running_gross += entry.fetch(:delta, 0.0).to_f.abs
            running_net[entry[:account]] += entry.fetch(:delta, 0.0).to_f
            next
          end

          delta = entry[:delta].to_f
          account = entry[:account]

          # Stage 2: Risk check using running exposure
          running_gross += delta.abs
          running_net[account] += delta

          collateral = running_net.values.map(&:abs).sum
          if RiskGate.limit_breached?(running_gross, collateral, leverage_cap)
            results << { account: account, status: :risk_blocked, gross: running_gross }
            next
          end

          # Stage 3: Compute fee for this entry
          fee = tiered_fee(delta.abs, fee_tiers)

          # Stage 4: Apply reserve
          net_after_reserve = (delta - delta.abs * reserve_ratio).round(6)
          results << {
            account: account,
            status: :settled,
            net: net_after_reserve,
            fee: fee,
            running_gross: running_gross
          }
        end

        { entries: results, final_gross: running_gross, final_net: running_net }
      end
    end
  end
end
