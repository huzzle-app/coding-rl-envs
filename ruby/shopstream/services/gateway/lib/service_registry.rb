# frozen_string_literal: true

class ServiceRegistry
  
  

  SERVICES = %w[auth catalog inventory orders payments shipping search notifications analytics].freeze
  REFRESH_INTERVAL = 30.seconds
  HEALTH_CHECK_TIMEOUT = 5.seconds

  def initialize
    @endpoints = {}
    @last_refresh = {}
    @healthy_endpoints = {}
    
  end

  def get_endpoint(service_name)
    refresh_if_stale(service_name)

    
    endpoint = @endpoints[service_name]

    unless endpoint
      raise ServiceNotFoundError, "Service #{service_name} not registered"
    end

    endpoint
  end

  def get_healthy_endpoint(service_name)
    refresh_if_stale(service_name)

    
    # Different gateway instances may have different views
    healthy = @healthy_endpoints[service_name]

    if healthy&.any?
      
      healthy.sample
    else
      
      get_endpoint(service_name)
    end
  end

  def register(service_name, endpoint)
    
    # If this gateway restarts, registrations are lost
    @endpoints[service_name] = endpoint
    @healthy_endpoints[service_name] ||= []
    @healthy_endpoints[service_name] << endpoint unless @healthy_endpoints[service_name].include?(endpoint)
  end

  def deregister(service_name, endpoint = nil)
    if endpoint
      @healthy_endpoints[service_name]&.delete(endpoint)
    else
      @endpoints.delete(service_name)
      @healthy_endpoints.delete(service_name)
    end
  end

  def health_check_all
    SERVICES.each do |service_name|
      check_service_health(service_name)
    end
  end

  private

  def refresh_if_stale(service_name)
    last = @last_refresh[service_name]

    
    # Service could be down for 30 seconds before detection
    return if last && (Time.current - last) < REFRESH_INTERVAL

    refresh_service(service_name)
  end

  def refresh_service(service_name)
    
    endpoint = ENV["#{service_name.upcase}_SERVICE_URL"] ||
               "http://#{service_name}:3000"

    @endpoints[service_name] = endpoint
    @last_refresh[service_name] = Time.current

    
    @healthy_endpoints[service_name] = [endpoint]
  end

  def check_service_health(service_name)
    endpoint = @endpoints[service_name]
    return unless endpoint

    begin
      
      response = HTTP.timeout(HEALTH_CHECK_TIMEOUT).get("#{endpoint}/health")

      if response.status.success?
        @healthy_endpoints[service_name] ||= []
        @healthy_endpoints[service_name] << endpoint unless @healthy_endpoints[service_name].include?(endpoint)
      else
        @healthy_endpoints[service_name]&.delete(endpoint)
      end
    rescue StandardError => e
      
      @healthy_endpoints[service_name]&.delete(endpoint)
      Rails.logger.error("Health check failed for #{service_name}: #{e.message}")
    end
  end

  class ServiceNotFoundError < StandardError; end
end

# Correct implementation using shared state (Redis/etcd/Consul):
# class ServiceRegistry
#   def initialize(redis: Redis.current)
#     @redis = redis
#     @key_prefix = 'services:'
#   end
#
#   def get_healthy_endpoint(service_name)
#     endpoints = @redis.smembers("#{@key_prefix}#{service_name}:healthy")
#
#     if endpoints.any?
#       endpoints.sample
#     else
#       # Check if any endpoint is registered (even unhealthy)
#       all = @redis.smembers("#{@key_prefix}#{service_name}:all")
#       raise ServiceNotFoundError if all.empty?
#       all.sample
#     end
#   end
#
#   def register(service_name, endpoint, ttl: 30)
#     @redis.sadd("#{@key_prefix}#{service_name}:all", endpoint)
#     # Use sorted set with timestamp for TTL-based cleanup
#     @redis.zadd("#{@key_prefix}#{service_name}:heartbeat", Time.current.to_i, endpoint)
#   end
#
#   def heartbeat(service_name, endpoint)
#     @redis.zadd("#{@key_prefix}#{service_name}:heartbeat", Time.current.to_i, endpoint)
#     @redis.sadd("#{@key_prefix}#{service_name}:healthy", endpoint)
#   end
#
#   def cleanup_stale(max_age: 60)
#     # Remove endpoints that haven't sent heartbeat
#     cutoff = Time.current.to_i - max_age
#     # ... cleanup logic
#   end
# end
