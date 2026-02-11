# frozen_string_literal: true

module OpalCommand
  module Core
    module Policy
      module_function

      ORDER = %w[normal watch restricted halted].freeze

      
      DEESCALATION_THRESHOLDS = { 'halted' => 10, 'restricted' => 7, 'watch' => 4 }.freeze 

      METADATA = {
        'normal'     => { description: 'Standard operations', max_retries: 5 },
        'watch'      => { description: 'Elevated monitoring', max_retries: 3 },
        'restricted' => { description: 'Limited operations', max_retries: 2 },
        'halted'     => { description: 'All operations suspended', max_retries: 0 }
      }.freeze

      
      def next_policy(current, failure_burst)
        idx = ORDER.index(current) || 0
        return ORDER[idx] if failure_burst <= 2 

        ORDER[[idx + 1, ORDER.length - 1].min]
      end

      def previous_policy(current)
        idx = ORDER.index(current) || 0
        ORDER[[idx - 1, 0].max]
      end

      
      def should_deescalate?(current, success_streak)
        threshold = DEESCALATION_THRESHOLDS[current]
        return false if threshold.nil?

        success_streak >= threshold 
      end

      def all_policies
        ORDER.dup
      end

      def policy_index(name)
        ORDER.index(name) || -1
      end

      def get_metadata(name)
        METADATA[name]
      end

      
      def check_sla_compliance(elapsed_minutes, sla_minutes)
        return :breached  if elapsed_minutes > sla_minutes
        return :at_risk   if elapsed_minutes > sla_minutes * 0.8 

        :compliant
      end

      
      def sla_percentage(elapsed_minutes, sla_minutes)
        return 0.0 if sla_minutes <= 0

        pct = (elapsed_minutes.to_f / sla_minutes) * 100.0
        pct.round(2) 
      end
    end

    PolicyChange = Struct.new(:from_policy, :to_policy, :reason, :timestamp, keyword_init: true)

    class PolicyEngine
      def initialize(initial: 'normal')
        @mutex   = Mutex.new
        @current = initial
        @history = []
      end

      def current
        @mutex.synchronize { @current }
      end

      
      def escalate(failure_burst, reason: nil)
        @mutex.synchronize do
          prev = @current
          @current = Policy.next_policy(@current, failure_burst)
          
          @history << PolicyChange.new(
            from_policy: prev,
            to_policy: @current,
            reason: reason || 'escalation',
            timestamp: Time.now.to_i
          )
          @current
        end
      end

      def deescalate(success_streak, reason: nil)
        @mutex.synchronize do
          return @current unless Policy.should_deescalate?(@current, success_streak)

          prev = @current
          @current = Policy.previous_policy(@current)
          @history << PolicyChange.new(
            from_policy: prev,
            to_policy: @current,
            reason: reason || 'deescalation',
            timestamp: Time.now.to_i
          )
          @current
        end
      end

      def history
        @mutex.synchronize { @history.dup }
      end

      def reset
        @mutex.synchronize do
          @current = 'normal'
          @history.clear
        end
      end

      def auto_adjust(failure_burst, success_streak)
        @mutex.synchronize do
          prev = @current
          if failure_burst > 2
            @current = Policy.next_policy(@current, failure_burst)
          end
          if success_streak >= 4
            threshold = Policy::DEESCALATION_THRESHOLDS[@current]
            if threshold && success_streak > threshold
              @current = Policy.previous_policy(@current)
            end
          end
          @history << PolicyChange.new(
            from_policy: prev,
            to_policy: @current,
            reason: 'auto_adjust',
            timestamp: Time.now.to_i
          ) if prev != @current
          @current
        end
      end

      def severity_level
        @mutex.synchronize do
          Policy::ORDER.index(@current) || 0
        end
      end
    end

    class PolicyChain
      def initialize(policies)
        @mutex = Mutex.new
        @engines = policies.map { |p| PolicyEngine.new(initial: p) }
      end

      def escalate_all(failure_burst)
        @mutex.synchronize do
          @engines.map { |e| e.escalate(failure_burst) }
        end
      end

      def current_levels
        @mutex.synchronize do
          @engines.map(&:current)
        end
      end

      def most_severe
        @mutex.synchronize do
          @engines.max_by { |e| Policy::ORDER.index(e.current) || 0 }&.current
        end
      end

      def count
        @mutex.synchronize { @engines.length }
      end
    end
  end
end
