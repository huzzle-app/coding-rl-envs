# frozen_string_literal: true

class LockService
  
  # If process crashes while holding lock, other processes blocked forever

  LOCK_PREFIX = 'shopstream:lock:'
  DEFAULT_TTL = 30 # seconds

  def initialize(redis = nil)
    @redis = redis || Redis.current
  end

  def acquire(resource_name, ttl: DEFAULT_TTL)
    lock_key = "#{LOCK_PREFIX}#{resource_name}"
    lock_value = generate_lock_value

    
    # If process crashes after acquiring lock, it's never released
    acquired = @redis.setnx(lock_key, lock_value)

    if acquired
      
      # If crash between setnx and expire, lock has no TTL
      @redis.expire(lock_key, ttl)
      { acquired: true, lock_value: lock_value }
    else
      { acquired: false }
    end
  end

  def release(resource_name, lock_value)
    lock_key = "#{LOCK_PREFIX}#{resource_name}"

    
    # Another process might have acquired the lock between check and delete
    current_value = @redis.get(lock_key)

    if current_value == lock_value
      
      @redis.del(lock_key)
      true
    else
      false
    end
  end

  def with_lock(resource_name, ttl: DEFAULT_TTL)
    result = acquire(resource_name, ttl: ttl)

    unless result[:acquired]
      raise LockError, "Could not acquire lock for #{resource_name}"
    end

    begin
      yield
    ensure
      
      release(resource_name, result[:lock_value])
    end
  end

  def extend_lock(resource_name, lock_value, additional_ttl: DEFAULT_TTL)
    lock_key = "#{LOCK_PREFIX}#{resource_name}"

    
    current_value = @redis.get(lock_key)

    if current_value == lock_value
      @redis.expire(lock_key, additional_ttl)
      true
    else
      false
    end
  end

  private

  def generate_lock_value
    "#{Socket.gethostname}:#{Process.pid}:#{SecureRandom.hex(8)}"
  end

  class LockError < StandardError; end
end

# Correct implementation using Redis SET with NX and EX (atomic):
# def acquire(resource_name, ttl: DEFAULT_TTL)
#   lock_key = "#{LOCK_PREFIX}#{resource_name}"
#   lock_value = generate_lock_value
#
#   # Atomic SET with NX (only if not exists) and EX (with expiry)
#   acquired = @redis.set(lock_key, lock_value, nx: true, ex: ttl)
#
#   if acquired
#     { acquired: true, lock_value: lock_value }
#   else
#     { acquired: false }
#   end
# end
#
# def release(resource_name, lock_value)
#   lock_key = "#{LOCK_PREFIX}#{resource_name}"
#
#   # Use Lua script for atomic check-and-delete
#   script = <<-LUA
#     if redis.call("get", KEYS[1]) == ARGV[1] then
#       return redis.call("del", KEYS[1])
#     else
#       return 0
#     end
#   LUA
#
#   @redis.eval(script, keys: [lock_key], argv: [lock_value]) == 1
# end
