# frozen_string_literal: true

module ShopStream
  # Request context for distributed tracing
  
  class RequestContext
    class << self
      def current
        Thread.current[:shopstream_request_context] ||= {}
      end

      def correlation_id
        current[:correlation_id]
      end

      def correlation_id=(value)
        current[:correlation_id] = value
      end

      def user_id
        current[:user_id]
      end

      def user_id=(value)
        current[:user_id] = value
      end

      def clear!
        Thread.current[:shopstream_request_context] = {}
      end

      def with(context)
        old_context = Thread.current[:shopstream_request_context]
        Thread.current[:shopstream_request_context] = context
        yield
      ensure
        Thread.current[:shopstream_request_context] = old_context
      end

      
      # to other services, so correlation ID is not propagated
      def propagate_headers
        {
          'X-Correlation-ID' => correlation_id,
          'X-User-ID' => user_id
        }.compact
      end

      
      def extract_from_request(request)
        self.correlation_id = request.headers['X-Correlation-ID'] || SecureRandom.uuid
        self.user_id = request.headers['X-User-ID']
      end
    end

    # Correct usage in middleware:
    # class RequestContextMiddleware
    #   def call(env)
    #     request = ActionDispatch::Request.new(env)
    #     RequestContext.extract_from_request(request)
    #     @app.call(env)
    #   ensure
    #     RequestContext.clear!
    #   end
    # end
    #
    # And when making HTTP calls:
    # HttpClient.new(url).get(path, headers: RequestContext.propagate_headers)
  end
end
