# frozen_string_literal: true

class TimeoutMiddleware
  
  # Gateway -> Orders -> Inventory -> Payments can exceed timeout

  
  DEFAULT_TIMEOUT = 5

  def initialize(app, timeout: DEFAULT_TIMEOUT)
    @app = app
    @timeout = timeout
  end

  def call(env)
    request = ActionDispatch::Request.new(env)

    
    # Some operations legitimately take longer
    timeout = determine_timeout(request)

    begin
      Timeout.timeout(timeout) do
        @app.call(env)
      end
    rescue Timeout::Error
      timeout_response(request)
    end
  end

  private

  def determine_timeout(request)
    
    # If this request calls Orders -> Inventory -> Payments,
    # each with 5s timeout, total could be 15s but we timeout at 5s

    
    # HttpClient has 3 retries, each could take 5s

    case request.path
    when %r{^/api/v1/orders}
      
      # 5s is not enough for: Orders + Inventory + Payments + Shipping
      @timeout
    when %r{^/api/v1/checkout}
      
      @timeout
    else
      @timeout
    end
  end

  def timeout_response(request)
    Rails.logger.error("Request timeout: #{request.method} #{request.path}")

    [
      504,
      { 'Content-Type' => 'application/json' },
      ['{"error": "Gateway Timeout", "message": "Request took too long to process"}']
    ]
  end
end

# Correct implementation:
# class TimeoutMiddleware
#   # Different timeouts for different operation types
#   TIMEOUTS = {
#     default: 5,
#     read: 3,
#     write: 10,
#     checkout: 30,  # Long chain
#     report: 60     # Reporting queries
#   }.freeze
#
#   def call(env)
#     request = ActionDispatch::Request.new(env)
#     timeout = determine_timeout(request)
#
#     # Set deadline header for downstream services
#     deadline = Time.current + timeout
#     env['HTTP_X_REQUEST_DEADLINE'] = deadline.iso8601
#
#     begin
#       Timeout.timeout(timeout) do
#         @app.call(env)
#       end
#     rescue Timeout::Error
#       timeout_response(request)
#     end
#   end
#
#   def determine_timeout(request)
#     case
#     when request.path.match?(%r{^/api/v1/checkout})
#       TIMEOUTS[:checkout]
#     when request.path.match?(%r{^/api/v1/reports})
#       TIMEOUTS[:report]
#     when request.get? || request.head?
#       TIMEOUTS[:read]
#     when request.post? || request.put? || request.patch?
#       TIMEOUTS[:write]
#     else
#       TIMEOUTS[:default]
#     end
#   end
# end
#
# # Downstream services should check deadline:
# def check_deadline
#   deadline = request.headers['HTTP_X_REQUEST_DEADLINE']
#   return unless deadline
#
#   if Time.parse(deadline) < Time.current
#     raise DeadlineExceeded, 'Request deadline exceeded'
#   end
# end
