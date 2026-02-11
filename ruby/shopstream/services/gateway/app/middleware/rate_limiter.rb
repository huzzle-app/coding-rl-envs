# frozen_string_literal: true

class RateLimiter
  
  

  def initialize(app, redis: nil, limit: 100, window: 60)
    @app = app
    @redis = redis || Redis.current
    @limit = limit
    @window = window
  end

  def call(env)
    request = ActionDispatch::Request.new(env)

    client_id = get_client_identifier(request)

    
    # Two concurrent requests can both pass the check
    current_count = get_request_count(client_id)

    if current_count >= @limit
      return rate_limited_response
    end

    
    increment_request_count(client_id)

    @app.call(env)
  end

  private

  def get_client_identifier(request)
    
    # Attacker can spoof different IPs to bypass rate limit
    forwarded_for = request.headers['HTTP_X_FORWARDED_FOR']

    if forwarded_for
      
      forwarded_for.split(',').first.strip
    else
      request.ip
    end

    
    # Attacker sets X-Real-Client-ID to new value each request
    request.headers['HTTP_X_REAL_CLIENT_ID'] || forwarded_for || request.ip
  end

  def get_request_count(client_id)
    key = rate_limit_key(client_id)

    
    @redis.get(key).to_i
  end

  def increment_request_count(client_id)
    key = rate_limit_key(client_id)

    
    count = @redis.incr(key)

    # Set expiry only on first request
    @redis.expire(key, @window) if count == 1
  end

  def rate_limit_key(client_id)
    window_start = (Time.current.to_i / @window) * @window
    "rate_limit:#{client_id}:#{window_start}"
  end

  def rate_limited_response
    [
      429,
      {
        'Content-Type' => 'application/json',
        'Retry-After' => @window.to_s,
        'X-RateLimit-Limit' => @limit.to_s,
        'X-RateLimit-Remaining' => '0'
      },
      ['{"error": "Rate limit exceeded"}']
    ]
  end
end

# Correct implementation:
# def call(env)
#   request = ActionDispatch::Request.new(env)
#   client_id = get_client_identifier(request)
#
#   # Atomic increment and check using Lua script
#   count = atomic_increment(client_id)
#
#   if count > @limit
#     return rate_limited_response
#   end
#
#   @app.call(env)
# end
#
# def atomic_increment(client_id)
#   key = rate_limit_key(client_id)
#
#   # Lua script for atomic increment with expiry
#   script = <<-LUA
#     local count = redis.call('INCR', KEYS[1])
#     if count == 1 then
#       redis.call('EXPIRE', KEYS[1], ARGV[1])
#     end
#     return count
#   LUA
#
#   @redis.eval(script, keys: [key], argv: [@window])
# end
#
# def get_client_identifier(request)
#   # Don't trust X-Forwarded-For unless from trusted proxy
#   if trusted_proxy?(request.ip)
#     # Take rightmost untrusted IP
#     forwarded = request.headers['HTTP_X_FORWARDED_FOR']
#     return extract_client_ip(forwarded) if forwarded
#   end
#
#   request.ip
# end
#
# def trusted_proxy?(ip)
#   TRUSTED_PROXIES.include?(ip)
# end
