# frozen_string_literal: true

class CircuitBreaker
  
  # State is stored in memory, not shared across instances

  STATES = %i[closed open half_open].freeze
  DEFAULT_THRESHOLD = 5
  DEFAULT_TIMEOUT = 30

  def initialize(service_name, threshold: DEFAULT_THRESHOLD, timeout: DEFAULT_TIMEOUT)
    @service_name = service_name
    @threshold = threshold
    @timeout = timeout

    
    # Each server instance has its own circuit breaker state
    # Service might be dead but circuit is closed on this instance
    @state = :closed
    @failure_count = 0
    @last_failure_time = nil
  end

  def call
    raise CircuitOpenError if open?

    begin
      result = yield

      
      # Other instances still think service is failing
      on_success
      result
    rescue StandardError => e
      on_failure(e)
      raise
    end
  end

  def open?
    case @state
    when :open
      
      if timeout_elapsed?
        @state = :half_open
        false
      else
        true
      end
    when :half_open
      false
    when :closed
      false
    end
  end

  def status
    {
      service: @service_name,
      state: @state,
      failure_count: @failure_count,
      last_failure: @last_failure_time
    }
  end

  private

  def on_success
    
    @failure_count = 0
    @state = :closed
  end

  def on_failure(error)
    @failure_count += 1
    @last_failure_time = Time.current

    
    # If 10 servers each see 4 failures (40 total), none open the circuit
    if @failure_count >= @threshold
      @state = :open
      Rails.logger.warn("Circuit opened for #{@service_name}")
    end
  end

  def timeout_elapsed?
    @last_failure_time.nil? || (Time.current - @last_failure_time) >= @timeout
  end

  class CircuitOpenError < StandardError; end
end

# Correct implementation using Redis for shared state:
# class CircuitBreaker
#   def initialize(service_name, redis: Redis.current, threshold: 5, timeout: 30)
#     @service_name = service_name
#     @redis = redis
#     @threshold = threshold
#     @timeout = timeout
#     @key_prefix = "circuit:#{service_name}"
#   end
#
#   def call
#     state = get_state
#     raise CircuitOpenError if state == 'open' && !timeout_elapsed?
#
#     begin
#       result = yield
#       on_success
#       result
#     rescue StandardError => e
#       on_failure(e)
#       raise
#     end
#   end
#
#   private
#
#   def get_state
#     @redis.get("#{@key_prefix}:state") || 'closed'
#   end
#
#   def set_state(state)
#     @redis.set("#{@key_prefix}:state", state)
#   end
#
#   def on_success
#     @redis.set("#{@key_prefix}:failure_count", 0)
#     set_state('closed')
#   end
#
#   def on_failure(error)
#     count = @redis.incr("#{@key_prefix}:failure_count")
#     @redis.set("#{@key_prefix}:last_failure", Time.current.to_i)
#
#     if count >= @threshold
#       set_state('open')
#     end
#   end
#
#   def timeout_elapsed?
#     last_failure = @redis.get("#{@key_prefix}:last_failure").to_i
#     (Time.current.to_i - last_failure) >= @timeout
#   end
# end
