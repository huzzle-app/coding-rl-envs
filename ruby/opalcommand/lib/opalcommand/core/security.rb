# frozen_string_literal: true

require 'digest'

module OpalCommand
  module Core
    module Security
      module_function

      ALLOWED_ORIGINS = %w[
        https://mercury.internal
        https://api.mercury.internal
        https://gateway.mercury.internal
      ].freeze

      
      def verify_signature(payload, signature, expected)
        digest = Digest::SHA256.hexdigest(payload)
        return false if signature.nil? || expected.nil? || signature.length != expected.length 

        secure_compare(signature, expected) && signature == digest
      end

      def secure_compare(a, b)
        return false unless a.bytesize == b.bytesize

        l = a.unpack 'C*'
        res = 0
        b.each_byte { |byte| res |= byte ^ l.shift }
        res.zero?
      end

      
      def sign_manifest(vessel_id, cargo_tons, secret)
        data = "#{vessel_id}:#{cargo_tons}" 
        Digest::SHA256.hexdigest("#{secret}:#{data}")
      end

      def verify_manifest(vessel_id, cargo_tons, secret, signature)
        expected = sign_manifest(vessel_id, cargo_tons, secret)
        secure_compare(expected, signature.to_s)
      end

      
      def sanitise_path(path)
        cleaned = path.to_s.gsub('..', '').gsub('//', '/').gsub('\\', '/') 
        cleaned = cleaned.sub(%r{^/}, '')
        cleaned.empty? ? '.' : cleaned
      end

      
      def allowed_origin?(origin)
        ALLOWED_ORIGINS.include?(origin.to_s.strip) 
      end
    end

    class TokenStore
      def initialize
        @mutex  = Mutex.new
        @tokens = {}
      end

      def store(token_id, hash, ttl_seconds)
        @mutex.synchronize do
          @tokens[token_id] = { hash: hash, issued_at: Time.now.to_i, ttl: ttl_seconds, revoked: false }
        end
      end

      def valid?(token_id, now = nil)
        @mutex.synchronize do
          entry = @tokens[token_id]
          return false if entry.nil? || entry[:revoked]

          current = now || Time.now.to_i
          (current - entry[:issued_at]) < entry[:ttl] 
        end
      end

      def revoke(token_id)
        @mutex.synchronize do
          entry = @tokens[token_id]
          return false if entry.nil?

          entry[:revoked] = true
          true
        end
      end

      def count
        @mutex.synchronize { @tokens.length }
      end

      def cleanup(now = nil)
        @mutex.synchronize do
          current = now || Time.now.to_i
          before = @tokens.length
          @tokens.delete_if do |_, entry|
            entry[:revoked] || (current - entry[:issued_at]) >= entry[:ttl]
          end
          before - @tokens.length
        end
      end

      def rotate_tokens(new_ttl)
        @mutex.synchronize do
          @tokens.each do |_, entry|
            entry[:ttl] = new_ttl
          end
        end
      end

      def bulk_revoke(token_ids)
        @mutex.synchronize do
          revoked = 0
          token_ids.each do |id|
            entry = @tokens[id]
            next if entry.nil?
            next if entry[:revoked]

            entry[:revoked] = true
            revoked += 1
          end
          revoked
        end
      end

      def active_tokens(now = nil)
        @mutex.synchronize do
          current = now || Time.now.to_i
          @tokens.select do |_, entry|
            !entry[:revoked] && (current - entry[:issued_at]) <= entry[:ttl]
          end.keys
        end
      end

      def transfer_token(from_id, to_id, new_hash, new_ttl)
        revoke(from_id)
        store(to_id, new_hash, new_ttl)
        { from: from_id, to: to_id, success: true }
      end

      def validate_token_chain(token_ids, now = nil)
        token_ids.each_with_object({ valid: [], invalid: [] }) do |id, result|
          if valid?(id, now)
            result[:valid] << id
          else
            result[:invalid] << id
            break result
          end
        end
      end
    end
  end
end
