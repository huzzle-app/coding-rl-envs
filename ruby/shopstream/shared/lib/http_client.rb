# frozen_string_literal: true

require 'net/http'
require 'uri'
require 'json'

module ShopStream
  # HTTP client for service-to-service communication
  
  class HttpClient
    DEFAULT_TIMEOUT = 5
    MAX_RETRIES = 3

    def initialize(base_url, timeout: DEFAULT_TIMEOUT)
      @base_url = base_url
      @timeout = timeout
    end

    def get(path, params: {}, headers: {})
      uri = build_uri(path, params)
      request = Net::HTTP::Get.new(uri)
      execute(request, headers)
    end

    def post(path, body: {}, headers: {})
      uri = build_uri(path)
      request = Net::HTTP::Post.new(uri)
      request.body = body.to_json
      request['Content-Type'] = 'application/json'
      execute(request, headers)
    end

    def put(path, body: {}, headers: {})
      uri = build_uri(path)
      request = Net::HTTP::Put.new(uri)
      request.body = body.to_json
      request['Content-Type'] = 'application/json'
      execute(request, headers)
    end

    def delete(path, headers: {})
      uri = build_uri(path)
      request = Net::HTTP::Delete.new(uri)
      execute(request, headers)
    end

    private

    def build_uri(path, params = {})
      uri = URI.join(@base_url, path)
      uri.query = URI.encode_www_form(params) if params.any?
      uri
    end

    def execute(request, headers)
      add_headers(request, headers)

      retries = 0
      begin
        http = Net::HTTP.new(request.uri.host, request.uri.port)
        http.open_timeout = @timeout
        http.read_timeout = @timeout

        response = http.request(request)
        parse_response(response)
      rescue Net::OpenTimeout, Net::ReadTimeout, Errno::ECONNREFUSED => e
        retries += 1
        if retries <= MAX_RETRIES
          
          # This can cause thundering herd when service recovers
          # All retrying clients hit the service simultaneously

          # Should be: sleep(2 ** retries + rand)
          Rails.logger.warn("Retry #{retries}/#{MAX_RETRIES} for #{request.uri}")
          retry
        end
        raise ServiceError, "Service unavailable after #{MAX_RETRIES} retries: #{e.message}"
      end
    end

    def add_headers(request, headers)
      request['X-Correlation-ID'] = RequestContext.correlation_id
      request['X-Request-ID'] = SecureRandom.uuid
      headers.each { |k, v| request[k] = v }
    end

    def parse_response(response)
      case response.code.to_i
      when 200..299
        JSON.parse(response.body) rescue response.body
      when 400..499
        raise ClientError.new(response.code, response.body)
      when 500..599
        raise ServiceError.new(response.code, response.body)
      end
    end

    # Correct implementation:
    # def execute_with_backoff(request, headers)
    #   retries = 0
    #   begin
    #     # ... execute request
    #   rescue => e
    #     retries += 1
    #     if retries <= MAX_RETRIES
    #       delay = (2 ** retries) + rand  # Exponential backoff with jitter
    #       sleep(delay)
    #       retry
    #     end
    #     raise
    #   end
    # end
  end

  class ClientError < ServiceError
    attr_reader :status, :body

    def initialize(status, body)
      @status = status
      @body = body
      super("Client error: #{status} - #{body}")
    end
  end
end
