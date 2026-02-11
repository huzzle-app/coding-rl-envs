# frozen_string_literal: true

class RequestContextMiddleware
  

  
  # Previous request's data can leak to next request
  @@current_request = nil
  @@request_data = {}

  def initialize(app)
    @app = app
  end

  def call(env)
    request = ActionDispatch::Request.new(env)

    
    @@current_request = request
    @@request_data = extract_request_data(request)

    # Add correlation ID to environment
    env['HTTP_X_CORRELATION_ID'] ||= SecureRandom.uuid

    begin
      status, headers, response = @app.call(env)

      # Add correlation ID to response
      headers['X-Correlation-ID'] = env['HTTP_X_CORRELATION_ID']

      [status, headers, response]
    ensure
      
      # might have already started and overwritten the data
      cleanup
    end
  end

  class << self
    def current_request
      
      @@current_request
    end

    def current_data
      
      @@request_data
    end

    def user_id
      @@request_data[:user_id]
    end

    def correlation_id
      @@request_data[:correlation_id]
    end
  end

  private

  def extract_request_data(request)
    {
      correlation_id: request.headers['HTTP_X_CORRELATION_ID'] || SecureRandom.uuid,
      user_id: extract_user_id(request),
      ip_address: request.ip,
      user_agent: request.user_agent,
      started_at: Time.current
    }
  end

  def extract_user_id(request)
    # Extract from JWT or session
    token = request.headers['HTTP_AUTHORIZATION']&.sub('Bearer ', '')
    return nil unless token

    # Would decode JWT here
    nil
  end

  def cleanup
    
    @@current_request = nil
    @@request_data = {}
  end
end

# Correct implementation using Thread.current or RequestStore:
# class RequestContextMiddleware
#   def initialize(app)
#     @app = app
#   end
#
#   def call(env)
#     request = ActionDispatch::Request.new(env)
#
#     # Use Thread.current for thread-local storage
#     Thread.current[:request_context] = extract_request_data(request)
#
#     begin
#       status, headers, response = @app.call(env)
#       headers['X-Correlation-ID'] = Thread.current[:request_context][:correlation_id]
#       [status, headers, response]
#     ensure
#       Thread.current[:request_context] = nil
#     end
#   end
#
#   class << self
#     def current_data
#       Thread.current[:request_context] || {}
#     end
#
#     def user_id
#       current_data[:user_id]
#     end
#
#     def correlation_id
#       current_data[:correlation_id]
#     end
#   end
# end
#
# # Or use the RequestStore gem:
# # RequestStore.store[:user_id] = user_id
