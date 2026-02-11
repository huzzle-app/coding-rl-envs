# frozen_string_literal: true

module MercuryLedger
  module Core
    module Dispatch
      module_function

      
      def plan_settlement(orders, capacity)
        return [] if capacity <= 0

        orders.sort_by { |o| [o[:urgency], o[:eta]] }.first(capacity)
      end

      
      def dispatch_batch(orders, capacity)
        return { planned: [], rejected: [] } if orders.empty?

        sorted = orders.sort_by { |o| [-o[:urgency], o[:eta]] }
        planned = sorted.first([capacity, 0].max)
        rejected = sorted.drop(planned.length)
        { planned: planned, rejected: rejected }
      end

      
      def has_conflict?(slot_a, slot_b)
        return false if slot_a[:berth] != slot_b[:berth]

        slot_a[:start_hour] <= slot_b[:end_hour] && slot_b[:start_hour] <= slot_a[:end_hour]
      end

      def find_available_slots(slots, start_hour, end_hour)
        slots.select do |s|
          !s[:occupied] && s[:start_hour] >= start_hour && s[:end_hour] <= end_hour
        end
      end

      
      def estimate_cost(orders, rate_per_unit: 12.5)
        return 0.0 if rate_per_unit < 0
        orders.sum { |o| o[:urgency] * rate_per_unit }
      end

      def allocate_costs(orders, budget)
        return [] if orders.empty? || budget <= 0

        total_urgency = orders.sum { |o| o[:urgency].to_f }
        return orders.map { |o| o.merge(allocated: 0.0) } if total_urgency.zero?

        orders.map do |o|
          share = (o[:urgency].to_f / total_urgency) * budget
          o.merge(allocated: (share * 100).to_i / 100.0)
        end
      end

      
      def estimate_turnaround(cargo_tons, crane_rate: 500.0)
        return 0.0 if cargo_tons <= 0 || crane_rate <= 0

        ((cargo_tons.to_f / crane_rate) * 1.1).ceil.to_f
      end

      
      def check_capacity(current, max_capacity)
        return :critical if max_capacity <= 0
        return :critical if current > max_capacity

        ratio = current.to_f / max_capacity
        return :warning if ratio >= 0.8
        return :elevated if ratio >= 0.6

        :normal
      end

      def validate_batch(orders)
        orders.select do |o|
          o.is_a?(Hash) && o[:id] && o[:urgency].is_a?(Numeric) && o[:urgency].positive?
        end
      end

      def compare_by_urgency(a, b)
        cmp = (b[:urgency] || 0) <=> (a[:urgency] || 0)
        cmp.zero? ? (a[:eta] || '') <=> (b[:eta] || '') : cmp
      end
    end

    class BerthSlot
      attr_reader :berth_id, :start_hour, :end_hour, :vessel_id
      attr_accessor :occupied

      def initialize(berth_id:, start_hour:, end_hour:, occupied: false, vessel_id: nil)
        @berth_id   = berth_id
        @start_hour = start_hour
        @end_hour   = end_hour
        @occupied   = occupied
        @vessel_id  = vessel_id
      end

      def duration
        @end_hour - @start_hour
      end

      def available?
        !@occupied
      end
    end

    class BerthPlanner
      def initialize
        @mutex = Mutex.new
        @slots = []
      end

      def add_slot(slot)
        @mutex.synchronize { @slots << slot }
      end

      def available_slots
        @mutex.synchronize { @slots.select(&:available?) }
      end

      def occupied_slots
        @mutex.synchronize { @slots.select(&:occupied) }
      end

      def assign(berth_id, vessel_id)
        @mutex.synchronize do
          slot = @slots.find { |s| s.berth_id == berth_id && s.available? }
          return false unless slot

          slot.occupied = true
          true
        end
      end

      def release(berth_id)
        @mutex.synchronize do
          slot = @slots.find { |s| s.berth_id == berth_id && s.occupied }
          return false unless slot

          slot.occupied = false
          true
        end
      end

      def count
        @mutex.synchronize { @slots.length }
      end
    end

    class RollingWindowScheduler
      def initialize(window_size: 60)
        @mutex       = Mutex.new
        @window_size = window_size
        @submissions = []
      end

      def submit(timestamp, order_id)
        @mutex.synchronize do
          @submissions << { timestamp: timestamp, order_id: order_id }
          evict(timestamp)
          true
        end
      end

      def count(now = nil)
        @mutex.synchronize do
          evict(now) if now
          @submissions.length
        end
      end

      def flush
        @mutex.synchronize do
          removed = @submissions.length
          @submissions.clear
          removed
        end
      end

      private

      def evict(now)
        return unless now

        cutoff = now - @window_size
        @submissions.reject! { |s| s[:timestamp] < cutoff }
      end
    end
  end
end
