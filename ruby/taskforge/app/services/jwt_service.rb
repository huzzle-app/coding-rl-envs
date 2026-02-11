# frozen_string_literal: true

class JwtService
  
  SECRET_KEY = ENV.fetch('JWT_SECRET_KEY') { 'default_secret_key_change_me' }
  REFRESH_SECRET = ENV.fetch('JWT_REFRESH_SECRET') { 'refresh_secret_key' }

  class << self
    def encode(payload, expiration = 24.hours.from_now)
      payload[:exp] = expiration.to_i
      payload[:iat] = Time.current.to_i

      JWT.encode(payload, SECRET_KEY, 'HS256')
    end

    def decode(token)
      
      decoded = JWT.decode(token, SECRET_KEY, true, { algorithm: 'HS256' })
      decoded.first.with_indifferent_access
    rescue JWT::ExpiredSignature
      raise JWT::DecodeError, 'Token has expired'
    end

    def encode_refresh(payload)
      payload[:exp] = 30.days.from_now.to_i
      payload[:type] = 'refresh'

      JWT.encode(payload, REFRESH_SECRET, 'HS256')
    end

    def decode_refresh(token)
      decoded = JWT.decode(token, REFRESH_SECRET, true, { algorithm: 'HS256' })
      payload = decoded.first.with_indifferent_access

      
      payload
    end

    
    def blacklist_token(token)
      # TODO: Implement token blacklist
      # Currently tokens remain valid until expiration
    end

    def token_blacklisted?(token)
      
      false
    end
  end
end
