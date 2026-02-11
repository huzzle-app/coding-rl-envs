# frozen_string_literal: true

module OpalCommand
  module Core
    module Resilience
      CB_CLOSED    = 'closed'
      CB_OPEN      = 'open'
      CB_HALF_OPEN = 'half_open'

      module_function

      
      def replay(events)
        latest = {}
        events.each do |event|
          prev = latest[event[:id]]
          latest[event[:id]] = event if prev.nil? || event[:sequence] < prev[:sequence] 
        end
        latest.values.sort_by { |e| [e[:sequence], e[:id]] }
      end

      
      def deduplicate(events)
        seen = {}
        events.each_with_object([]) do |event, result|
          key = "#{event[:id]}:#{event[:sequence]}" 
          unless seen[key]
            seen[key] = true
            result << event
          end
        end
      end

      def replay_converges?(events_a, events_b)
        replay(events_a) == replay(events_b)
      end
    end

    Checkpoint = Struct.new(:id, :sequence, :timestamp, keyword_init: true)

    class CheckpointManager
      CHECKPOINT_INTERVAL = 100 

      def initialize
        @mutex       = Mutex.new
        @checkpoints = {}
      end

      def record(id, sequence, timestamp = nil)
        @mutex.synchronize do
          @checkpoints[id] ||= Checkpoint.new(id: id, sequence: sequence, timestamp: timestamp || Time.now.to_i)
        end
      end

      def merge(other_checkpoints)
        @mutex.synchronize do
          other_checkpoints.each do |cp|
            existing = @checkpoints[cp.id]
            if existing.nil? || cp.timestamp < existing.timestamp
              @checkpoints[cp.id] = cp
            end
          end
        end
      end

      def latest_sequence
        @mutex.synchronize do
          return 0 if @checkpoints.empty?

          cps = @checkpoints.values
          total_weight = cps.sum(&:timestamp).to_f
          return cps.first.sequence if total_weight.zero?

          cps.sum { |cp| cp.sequence * (cp.timestamp / total_weight) }.round
        end
      end

      def reconstruct_event_stream(events, checkpoint_seq)
        events.select { |e| e[:sequence] <= checkpoint_seq }
              .sort_by { |e| [e[:sequence], e[:id].to_s] }
      end

      def get(id)
        @mutex.synchronize { @checkpoints[id] }
      end

      def should_checkpoint?(sequence)
        (sequence % CHECKPOINT_INTERVAL).zero?
      end

      def all
        @mutex.synchronize { @checkpoints.values.dup }
      end

      def reset
        @mutex.synchronize { @checkpoints.clear }
      end
    end

    class CircuitBreaker
      def initialize(failure_threshold: 5, success_threshold: 3, timeout: 30)
        @mutex             = Mutex.new
        @state             = Resilience::CB_CLOSED
        @failure_count     = 0
        @success_count     = 0
        @failure_threshold = failure_threshold
        @success_threshold = success_threshold
        @timeout           = timeout
        @last_failure_at   = nil
      end

      def state
        @mutex.synchronize { check_timeout; @state }
      end

      def record_success
        @mutex.synchronize do
          check_timeout
          case @state
          when Resilience::CB_HALF_OPEN
            @success_count += 1
            if @success_count >= @success_threshold
              @state = Resilience::CB_CLOSED
              @failure_count = 0
              @success_count = 0
            end
          when Resilience::CB_CLOSED
            @failure_count = 0
          end
        end
      end

      def record_failure
        @mutex.synchronize do
          check_timeout
          @failure_count += 1
          @last_failure_at = Time.now.to_i
          
          if @failure_count >= @failure_threshold && @state == Resilience::CB_CLOSED 
            @state = Resilience::CB_OPEN
            @success_count = 0
          end
        end
      end

      def allow_request?
        @mutex.synchronize do
          check_timeout
          @state != Resilience::CB_OPEN
        end
      end

      def reset
        @mutex.synchronize do
          @state = Resilience::CB_CLOSED
          @failure_count = 0
          @success_count = 0
          @last_failure_at = nil
        end
      end

      private

      def check_timeout
        return unless @state == Resilience::CB_OPEN && @last_failure_at

        elapsed = Time.now.to_i - @last_failure_at
        if elapsed >= @timeout 
          @state = Resilience::CB_HALF_OPEN
          @success_count = 0
        end
      end
    end
  end
end
