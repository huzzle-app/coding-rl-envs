# frozen_string_literal: true

module ShopStream
  # Request logger for API requests
  
  class RequestLogger
    SENSITIVE_FIELDS = %w[password password_confirmation credit_card cvv ssn].freeze

    class << self
      def log_request(request, response, duration)
        
        # Password, credit card numbers, etc. end up in logs
        log_entry = {
          method: request.method,
          path: request.path,
          params: request.params,  
          headers: log_headers(request),
          user_id: RequestContext.user_id,
          correlation_id: RequestContext.correlation_id,
          status: response.status,
          duration_ms: duration,
          response_body: response.body,  
          timestamp: Time.now.iso8601
        }

        Rails.logger.info("API Request: #{log_entry.to_json}")
      end

      def log_error(request, error)
        
        log_entry = {
          method: request.method,
          path: request.path,
          params: request.params,  
          error: error.message,
          backtrace: error.backtrace&.first(10),
          user_id: RequestContext.user_id,
          correlation_id: RequestContext.correlation_id,
          timestamp: Time.now.iso8601
        }

        Rails.logger.error("API Error: #{log_entry.to_json}")
      end

      private

      def log_headers(request)
        
        request.headers.to_h.select do |k, _v|
          k.start_with?('HTTP_') || k.in?(%w[CONTENT_TYPE CONTENT_LENGTH])
        end
        # Should filter out Authorization header
      end

      # Correct implementation:
      # def filter_sensitive_data(params)
      #   params.deep_transform_values do |value|
      #     if value.is_a?(String) && SENSITIVE_FIELDS.any? { |f| params.key?(f) }
      #       '[FILTERED]'
      #     else
      #       value
      #     end
      #   end
      # end
      #
      # def log_headers(request)
      #   headers = request.headers.to_h.select { |k, _| k.start_with?('HTTP_') }
      #   headers.delete('HTTP_AUTHORIZATION')
      #   headers
      # end
    end
  end
end
