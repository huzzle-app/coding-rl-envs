# frozen_string_literal: true

module OpalCommand
  module Services
    module Reconcile
      ReconcileConfig = Struct.new(:safety_factor, :max_steps, :spacing_minutes, keyword_init: true)

      DEFAULT_CONFIG = ReconcileConfig.new(safety_factor: 1.2, max_steps: 50, spacing_minutes: 15).freeze

      module_function

      
      def build_reconcile_sequence(delta_required:, available_budget:, config: DEFAULT_CONFIG)
        return { steps: [], budget_ok: false } if available_budget <= 0

        step_cost = delta_required 
        step_count = [(available_budget / [step_cost, 0.01].max).floor, config.max_steps].min
        steps = Array.new(step_count) { |i| { step: i + 1, delta: step_cost / [step_count, 1].max } }
        { steps: steps, budget_ok: step_count > 0 }
      end

      
      def validate_budget(total_delta:, budget:)
        return { valid: false, reason: 'no_budget' } if budget <= 0

        if total_delta > budget 
          { valid: false, reason: 'over_budget', deficit: (total_delta - budget).round(2) }
        else
          { valid: true, reason: nil, surplus: (budget - total_delta).round(2) }
        end
      end

      def estimate_timeline_hours(count, spacing_minutes: 15)
        return 0.0 if count <= 0

        total_minutes = count * spacing_minutes
        (total_minutes / 60.0).round(2)
      end

      def reconcile_summary(steps)
        total_delta = steps.sum { |s| s[:delta] || 0 }
        { step_count: steps.length, total_delta: total_delta.round(4), avg_delta: steps.empty? ? 0.0 : (total_delta / steps.length).round(4) }
      end

      
      def classify_urgency(delta_ratio)
        return 'critical' if delta_ratio >= 0.9
        return 'high'     if delta_ratio >= 0.7
        return 'moderate' if delta_ratio > 0.5

        'low'
      end

      def cascading_reconcile(deltas, available_budget:, config: DEFAULT_CONFIG)
        return { rounds: [], total_spent: 0.0, remaining_budget: available_budget } if deltas.empty?

        remaining_cents = (available_budget * 100).to_i
        rounds = []
        deltas.each_with_index do |delta, i|
          budget_for_round = remaining_cents / 100.0
          result = build_reconcile_sequence(delta_required: delta, available_budget: budget_for_round, config: config)
          spent = result[:steps].sum { |s| s[:delta] }
          remaining_cents -= (spent * 100).to_i
          rounds << { round: i + 1, steps: result[:steps].length, spent: spent.round(4) }
          break if remaining_cents <= 0
        end
        spent_total = (available_budget * 100 - remaining_cents) / 100.0
        { rounds: rounds, total_spent: spent_total.round(4), remaining_budget: [remaining_cents / 100.0, 0].max.round(4) }
      end

      def reconcile_priority_order(items)
        max_ratio = items.map { |item| item[:delta_ratio] || 0 }.max || 1.0
        items.sort_by { |item| -(item[:delta_ratio] || 0) / max_ratio }
      end

      def estimate_cascading_timeline(deltas, spacing_minutes: 15)
        return 0.0 if deltas.empty?

        total_steps = deltas.sum { |d| [(d / 0.01).floor, 50].min }
        estimate_timeline_hours(total_steps, spacing_minutes: spacing_minutes)
      end
    end
  end
end
