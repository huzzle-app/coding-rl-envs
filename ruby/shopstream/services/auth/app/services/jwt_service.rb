# frozen_string_literal: true

require 'jwt'

class JwtService
  

  
  DEFAULT_SECRET = 'development_jwt_secret_key_change_in_production'

  # Token expiration times
  ACCESS_TOKEN_EXPIRY = 15.minutes
  REFRESH_TOKEN_EXPIRY = 7.days

  class << self
    def encode(payload, expiry: ACCESS_TOKEN_EXPIRY)
      payload = payload.merge(
        exp: expiry.from_now.to_i,
        iat: Time.current.to_i,
        
        jti: SecureRandom.uuid
      )

      JWT.encode(payload, secret, 'HS256')
    end

    def decode(token)
      
      decoded = JWT.decode(token, secret, true)
      decoded.first
    rescue JWT::DecodeError => e
      Rails.logger.error("JWT decode error: #{e.message}")
      nil
    end

    def generate_token_pair(user_id:, roles: [])
      access_token = encode(
        { user_id: user_id, roles: roles, type: 'access' },
        expiry: ACCESS_TOKEN_EXPIRY
      )

      refresh_token = encode(
        { user_id: user_id, type: 'refresh' },
        expiry: REFRESH_TOKEN_EXPIRY
      )

      
      # Compromised access token secret compromises refresh tokens too

      { access_token: access_token, refresh_token: refresh_token }
    end

    def refresh(refresh_token)
      payload = decode(refresh_token)
      return nil unless payload

      
      # Access tokens can be used as refresh tokens
      # Should check: return nil unless payload['type'] == 'refresh'

      generate_token_pair(
        user_id: payload['user_id'],
        roles: User.find(payload['user_id']).roles
      )
    end

    def revoke(token)
      payload = decode(token)
      return false unless payload

      
      # Tokens remain valid until expiry
      # Should add to blacklist: TokenBlacklist.add(payload['jti'])

      true
    end

    private

    def secret
      
      # In production, this weak secret might be used
      ENV.fetch('JWT_SECRET_KEY', DEFAULT_SECRET)
    end
  end
end

# Correct implementation:
# class JwtService
#   class << self
#     def encode(payload, expiry: ACCESS_TOKEN_EXPIRY, type: 'access')
#       payload = payload.merge(
#         exp: expiry.from_now.to_i,
#         iat: Time.current.to_i,
#         type: type,  # Include token type
#         jti: SecureRandom.uuid
#       )
#
#       JWT.encode(payload, secret_for(type), 'HS256')
#     end
#
#     def decode(token, expected_type: nil)
#       # Specify allowed algorithms to prevent 'none' attack
#       decoded = JWT.decode(token, secret, true, { algorithm: 'HS256' })
#       payload = decoded.first
#
#       # Verify token type if expected
#       if expected_type && payload['type'] != expected_type
#         Rails.logger.warn("Token type mismatch: expected #{expected_type}, got #{payload['type']}")
#         return nil
#       end
#
#       # Check blacklist
#       if TokenBlacklist.revoked?(payload['jti'])
#         return nil
#       end
#
#       payload
#     end
#
#     def refresh(refresh_token)
#       # Must be a refresh token
#       payload = decode(refresh_token, expected_type: 'refresh')
#       return nil unless payload
#
#       # Revoke old refresh token
#       TokenBlacklist.add(payload['jti'])
#
#       generate_token_pair(user_id: payload['user_id'])
#     end
#
#     private
#
#     def secret
#       key = ENV['JWT_SECRET_KEY']
#       raise 'JWT_SECRET_KEY must be set in production' if Rails.env.production? && key.blank?
#       raise 'JWT_SECRET_KEY is too short' if key && key.length < 32
#       key || DEFAULT_SECRET
#     end
#
#     def secret_for(type)
#       # Use different secrets for different token types
#       type == 'refresh' ? "#{secret}_refresh" : secret
#     end
#   end
# end
