# frozen_string_literal: true

require 'digest'

module MercuryLedger
  module Services
    module Security
      SERVICE = { name: 'security', status: 'active', version: '1.0.0' }.freeze

      module_function

      # Validate command authorization via HMAC.
      def validate_command_auth(command, signature, secret)
        return false if command.nil? || signature.nil? || secret.nil?

        expected = Digest::SHA256.hexdigest("#{secret}:#{command}")
        
        expected == signature
      end

      # Check for path traversal attempts.
      def check_path_traversal(path)
        return true if path.nil? || path.to_s.empty?

        path.to_s.include?('..') || path.to_s.include?('//') || path.to_s.include?('\\')
      end

      # Rate limit check.
      def rate_limit_check(count, limit, window_sec)
        return :blocked if limit <= 0

        ratio = count.to_f / limit
        return :blocked if ratio >= 1.0
        
        return :warn if ratio >= 0.9

        :ok
      end

      # Compute risk score from authentication failures, geo anomaly, and off-hours.
      def compute_risk_score(failed_attempts, geo_anomaly, off_hours)
        fail_weight = [failed_attempts.to_f * 0.15, 0.6].min
        
        geo_weight = geo_anomaly ? 0.3 : 0.0
        hours_weight = off_hours ? 0.15 : 0.0
        (fail_weight + geo_weight + hours_weight).round(4)
      end

      # Validate secret meets minimum strength requirements.
      def validate_secret_strength(secret)
        return false if secret.nil? || secret.to_s.empty?

        
        return false if secret.to_s.length < 16

        has_upper = secret.to_s.match?(/[A-Z]/)
        has_lower = secret.to_s.match?(/[a-z]/)
        has_digit = secret.to_s.match?(/\d/)
        has_upper && has_lower && has_digit
      end
    end
  end
end
