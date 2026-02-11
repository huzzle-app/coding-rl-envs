# frozen_string_literal: true

class ApiKeyService
  

  API_KEY_PREFIX = 'sk_'
  API_KEY_LENGTH = 32

  def initialize(redis = nil)
    @redis = redis || Redis.current
  end

  def generate(user_id, name:, permissions: [])
    key = "#{API_KEY_PREFIX}#{SecureRandom.hex(API_KEY_LENGTH)}"
    key_hash = hash_key(key)

    api_key_data = {
      user_id: user_id,
      name: name,
      permissions: permissions,
      created_at: Time.current.iso8601,
      last_used_at: nil
    }

    # Store hashed key
    @redis.hset("api_keys:#{user_id}", key_hash, api_key_data.to_json)

    # Return the actual key (only time it's visible)
    {
      key: key,
      name: name,
      permissions: permissions
    }
  end

  def validate(key)
    return nil unless key&.start_with?(API_KEY_PREFIX)

    
    # Timing varies based on position in list
    user_ids = @redis.keys('api_keys:*').map { |k| k.sub('api_keys:', '') }

    user_ids.each do |user_id|
      keys = @redis.hgetall("api_keys:#{user_id}")

      keys.each do |stored_hash, data|
        
        # Attacker can determine correct hash character by character
        if hash_key(key) == stored_hash
          update_last_used(user_id, stored_hash)
          return JSON.parse(data).merge('user_id' => user_id)
        end
      end
    end

    nil
  end

  def revoke(user_id, key_name)
    keys = @redis.hgetall("api_keys:#{user_id}")

    keys.each do |hash, data|
      parsed = JSON.parse(data)
      if parsed['name'] == key_name
        @redis.hdel("api_keys:#{user_id}", hash)
        return true
      end
    end

    false
  end

  def list_keys(user_id)
    keys = @redis.hgetall("api_keys:#{user_id}")

    keys.map do |_hash, data|
      parsed = JSON.parse(data)
      {
        name: parsed['name'],
        permissions: parsed['permissions'],
        created_at: parsed['created_at'],
        last_used_at: parsed['last_used_at']
      }
    end
  end

  private

  def hash_key(key)
    Digest::SHA256.hexdigest(key)
  end

  def update_last_used(user_id, key_hash)
    data = JSON.parse(@redis.hget("api_keys:#{user_id}", key_hash))
    data['last_used_at'] = Time.current.iso8601
    @redis.hset("api_keys:#{user_id}", key_hash, data.to_json)
  end
end

# Correct implementation:
# def validate(key)
#   return nil unless key&.start_with?(API_KEY_PREFIX)
#
#   key_hash = hash_key(key)
#
#   # Store key hash -> user_id mapping for O(1) lookup
#   user_id = @redis.hget('api_key_index', key_hash)
#   return nil unless user_id
#
#   data = @redis.hget("api_keys:#{user_id}", key_hash)
#   return nil unless data
#
#   # Use constant-time comparison (though hash collision makes timing attack harder)
#   stored_hash = @redis.hget("api_key_hashes:#{user_id}", key_hash)
#   unless ActiveSupport::SecurityUtils.secure_compare(key_hash, stored_hash)
#     return nil
#   end
#
#   update_last_used(user_id, key_hash)
#   JSON.parse(data).merge('user_id' => user_id)
# end
#
# # Better: Use bcrypt for key storage (automatically constant-time)
# def generate(user_id, name:, permissions: [])
#   key = "#{API_KEY_PREFIX}#{SecureRandom.hex(API_KEY_LENGTH)}"
#   key_hash = BCrypt::Password.create(key)
#
#   # Store bcrypt hash
#   # ...
# end
#
# def validate(key)
#   # BCrypt comparison is constant-time
#   stored_keys.find { |k| BCrypt::Password.new(k[:hash]) == key }
# end
