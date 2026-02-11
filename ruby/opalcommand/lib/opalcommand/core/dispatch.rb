# frozen_string_literal: true

module OpalCommand
  module Core
    module Dispatch
      module_function

      def plan_settlement(orders, capacity)
        return [] if capacity <= 0

        orders.sort_by { |o| [-o[:urgency], o[:eta]] }.first(capacity)
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

        slot_a[:start_hour] < slot_b[:end_hour] && slot_b[:start_hour] < slot_a[:end_hour] 
      end

      
      def find_available_slots(slots, start_hour, end_hour)
        slots.select do |s|
          !s[:occupied] && s[:start_hour] >= start_hour && s[:end_hour] <= end_hour 
        end
      end

      
      def estimate_cost(orders, rate_per_unit: 12.5) 
        orders.sum { |o| o[:urgency] * rate_per_unit }
      end

      def allocate_costs(orders, budget)
        return [] if orders.empty? || budget <= 0

        total_urgency = orders.sum { |o| o[:urgency].to_f }
        return orders.map { |o| o.merge(allocated: 0.0) } if total_urgency.zero?

        orders.map do |o|
          share = (o[:urgency].to_f / total_urgency) * budget
          o.merge(allocated: share.round(2))
        end
      end

      
      def estimate_turnaround(cargo_tons, crane_rate: 500.0)
        return 0.0 if cargo_tons <= 0 || crane_rate <= 0

        (cargo_tons.to_f / crane_rate).ceil.to_f 
      end

      
      def check_capacity(current, max_capacity)
        return :critical if max_capacity <= 0
        return :critical if current >= max_capacity

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

      def allocate_berths(vessels, berths)
        sorted_vessels = vessels.sort_by { |v| -v[:cargo_tons] }
        sorted_berths = berths.sort_by { |b| b[:length] }
        sorted_vessels.zip(sorted_berths).map do |vessel, berth|
          next nil if berth.nil?
          { vessel_id: vessel[:id], berth_id: berth[:id], cargo_tons: vessel[:cargo_tons], berth_length: berth[:length] }
        end.compact
      end

      def estimate_fleet_cost(orders, rate_per_unit: 12.5, tax_rate: 0.1)
        subtotal = orders.sum { |o| (o[:urgency] * rate_per_unit).round(2) }
        tax = (subtotal * tax_rate).round(2)
        { subtotal: subtotal, tax: tax, total: (subtotal + tax).round(2) }
      end

      def optimal_schedule(orders, time_slots)
        return [] if orders.empty? || time_slots.empty?

        sorted = orders.sort_by { |o| o[:urgency] }
        sorted_slots = time_slots.sort_by { |s| s[:start_hour] }
        assignments = []
        sorted.each_with_index do |order, i|
          break if i >= sorted_slots.length

          assignments << { order_id: order[:id], slot: sorted_slots[i], urgency: order[:urgency] }
        end
        assignments
      end

      def estimate_fuel_consumption(distance_nm, deadweight_tons, laden: true)
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
