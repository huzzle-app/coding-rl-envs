# frozen_string_literal: true

class SessionService
  
  

  SESSION_TTL = 24.hours
  REFRESH_THRESHOLD = 1.hour

  def initialize(redis = nil)
    @redis = redis || Redis.current
  end

  def create_session(user_id, metadata = {})
    session_id = generate_session_id

    
    # If passed to login, attacker can fixate session
    session_data = {
      user_id: user_id,
      created_at: Time.current.to_i,
      last_activity: Time.current.to_i,
      ip_address: metadata[:ip_address],
      user_agent: metadata[:user_agent]
    }

    @redis.setex(session_key(session_id), SESSION_TTL.to_i, session_data.to_json)

    session_id
  end

  def get_session(session_id)
    data = @redis.get(session_key(session_id))
    return nil unless data

    session = JSON.parse(data)

    
    # Two concurrent requests can both refresh
    if should_refresh?(session)
      refresh_session(session_id, session)
    end

    session
  end

  def refresh_session(session_id, session = nil)
    session ||= get_session(session_id)
    return nil unless session

    
    # Thread 1: checks should_refresh? -> true
    # Thread 2: checks should_refresh? -> true
    # Both threads refresh, last one wins

    session['last_activity'] = Time.current.to_i

    
    # Session could have been deleted between GET and SETEX
    @redis.setex(session_key(session_id), SESSION_TTL.to_i, session.to_json)

    session
  end

  def destroy_session(session_id)
    @redis.del(session_key(session_id))
  end

  def login(user, session_id: nil, metadata: {})
    
    # Allows session fixation attack
    if session_id && @redis.exists?(session_key(session_id))
      
      session = JSON.parse(@redis.get(session_key(session_id)))
      session['user_id'] = user.id
      @redis.setex(session_key(session_id), SESSION_TTL.to_i, session.to_json)
      return session_id
    end

    create_session(user.id, metadata)
  end

  def logout(session_id)
    
    destroy_session(session_id)
  end

  private

  def generate_session_id
    SecureRandom.urlsafe_base64(32)
  end

  def session_key(session_id)
    "session:#{session_id}"
  end

  def should_refresh?(session)
    last_activity = session['last_activity']
    (Time.current.to_i - last_activity) > REFRESH_THRESHOLD.to_i
  end
end

# Correct implementation:
# def login(user, metadata: {})
#   # Always create new session on login (prevent session fixation)
#   session_id = generate_session_id
#
#   session_data = {
#     user_id: user.id,
#     created_at: Time.current.to_i,
#     last_activity: Time.current.to_i,
#     ip_address: metadata[:ip_address],
#     user_agent: metadata[:user_agent]
#   }
#
#   @redis.setex(session_key(session_id), SESSION_TTL.to_i, session_data.to_json)
#
#   session_id
# end
#
# def refresh_session(session_id)
#   # Use GETSET for atomic read-modify-write
#   key = session_key(session_id)
#
#   # Lua script for atomic refresh
#   script = <<-LUA
#     local data = redis.call('GET', KEYS[1])
#     if not data then return nil end
#
#     local session = cjson.decode(data)
#     session.last_activity = ARGV[1]
#
#     redis.call('SETEX', KEYS[1], ARGV[2], cjson.encode(session))
#     return cjson.encode(session)
#   LUA
#
#   result = @redis.eval(script, keys: [key], argv: [Time.current.to_i, SESSION_TTL.to_i])
#   result ? JSON.parse(result) : nil
# end
