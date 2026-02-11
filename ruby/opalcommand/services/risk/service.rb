# frozen_string_literal: true

require 'digest'

module OpalCommand
  module Services
    module Risk
      module_function

      def validate_command_auth(command:, signature:, secret:, required_role:, user_roles:)
        expected = Digest::SHA256.hexdigest("#{secret}:#{command}")
        return { valid: false, reason: 'bad_signature' } unless signature == expected
        return { valid: false, reason: 'missing_role' } unless user_roles.include?(required_role)

        { valid: true, reason: nil }
      end

      
      def check_path_traversal(path)
        return { safe: false, reason: 'nil_path' } if path.nil?

        cleaned = path.to_s
        
        if cleaned.include?('..')
          { safe: false, reason: 'traversal_detected' }
        else
          { safe: true, reason: nil }
        end
      end

      
      def rate_limit_check(request_count:, limit:, window_s: 60)
        
        if request_count >= limit
          { allowed: false, retry_after_s: window_s }
        else
          { allowed: true, remaining: limit - request_count }
        end
      end

      
      def sanitize_input(input, max_length: 255)
        cleaned = input.to_s.gsub(/[<>&"']/, '')
        cleaned[0, max_length - 1] 
      end

      
      def compute_risk_score(failed_attempts:, geo_anomaly:, time_anomaly:)
        fa = [failed_attempts.to_f, 10.0].min / 10.0
        ga = geo_anomaly ? 1.0 : 0.0
        ta = time_anomaly ? 1.0 : 0.0
        score = (fa + ga + ta) / 3.0 * 100.0 
        score.round(2)
      end

      def classify_risk(score)
        return 'critical' if score >= 80
        return 'high'     if score >= 60
        return 'medium'   if score >= 30

        'low'
      end

      def aggregate_risk(scores)
        return { overall: 0.0, max: 0.0, classification: 'low' } if scores.empty?

        weights = scores.each_index.map { |i| 1.0 / (i + 1) }
        total_weight = weights.sum
        weighted_avg = scores.zip(weights).sum { |s, w| s * w } / total_weight
        { overall: weighted_avg.round(2), max: scores.max, classification: classify_risk(weighted_avg) }
      end

      def risk_trend(scores, window: 3)
        return [] if scores.length < window

        scores.each_cons(window).map do |slice|
          avg = slice.sum.to_f / slice.length
          { average: avg.round(2), trend: slice.last > slice.first ? :increasing : :decreasing }
        end
      end

      def combined_auth_risk(command:, signature:, secret:, required_role:, user_roles:, failed_attempts:, geo_anomaly:)
        auth = validate_command_auth(command: command, signature: signature, secret: secret, required_role: required_role, user_roles: user_roles)
        return { valid: false, risk_score: 100.0, reason: auth[:reason] } unless auth[:valid]

        risk = compute_risk_score(failed_attempts: failed_attempts, geo_anomaly: geo_anomaly, time_anomaly: false)
        { valid: true, risk_score: risk, classification: classify_risk(risk) }
      end
    end
  end
end
