# frozen_string_literal: true

module MercuryLedger
  module Core
    module Queue
      
      DEFAULT_HARD_LIMIT = 100
      EMERGENCY_RATIO    = 0.8
      
      WARN_RATIO         = 0.6

      module_function

      
      def should_shed?(depth, hard_limit, emergency)
        return true if hard_limit <= 0
        return true if emergency && depth >= (hard_limit * EMERGENCY_RATIO).to_i

        depth >= hard_limit
      end

      
      def estimate_wait_time(depth, processing_rate)
        return 0.0 if processing_rate <= 0

        (depth.to_f / processing_rate).round(2)
      end
    end

    QueueHealth = Struct.new(:depth, :hard_limit, :status, :utilization, keyword_init: true)

    module QueueMonitor
      module_function

      def queue_health(depth, hard_limit)
        return QueueHealth.new(depth: depth, hard_limit: hard_limit, status: :critical, utilization: 1.0) if hard_limit <= 0

        util = depth.to_f / hard_limit
        status = if util >= 1.0
                   :critical
                 elsif util >= Queue::EMERGENCY_RATIO
                   :danger
                 elsif util >= Queue::WARN_RATIO
                   :warning
                 else
                   :healthy
                 end
        QueueHealth.new(depth: depth, hard_limit: hard_limit, status: status, utilization: util.round(4))
      end
    end

    class PriorityQueue
      def initialize
        @mutex = Mutex.new
        @items = []
      end

      def enqueue(item, priority)
        @mutex.synchronize do
          @items << { item: item, priority: priority }
          @items.sort_by! { |e| -e[:priority] }
        end
      end

      def dequeue
        @mutex.synchronize { @items.shift&.fetch(:item) }
      end

      def peek
        @mutex.synchronize { @items.first&.fetch(:item) }
      end

      def size
        @mutex.synchronize { @items.length }
      end

      def empty?
        @mutex.synchronize { @items.empty? }
      end

      
      def drain
        @mutex.synchronize do
          result = @items.map { |e| e[:item] }
          @items.clear
          result
        end
      end

      def clear
        @mutex.synchronize { @items.clear }
      end
    end

    class RateLimiter
      def initialize(max_tokens: 10, refill_rate: 1.0)
        @mutex       = Mutex.new
        @max_tokens  = max_tokens
        @tokens      = max_tokens.to_f
        @refill_rate = refill_rate
        @last_refill = Time.now.to_f
      end

      def allow?(now = nil)
        @mutex.synchronize do
          refill(now)
          return false if @tokens <= 0

          @tokens -= 1.0
          true
        end
      end

      def tokens
        @mutex.synchronize { @tokens.floor }
      end

      private

      def refill(now)
        current = now || Time.now.to_f
        elapsed = current - @last_refill
        return if elapsed <= 0

        @tokens = [@tokens + elapsed * @refill_rate, @max_tokens.to_f].min
        @last_refill = current
      end
    end
  end
end
