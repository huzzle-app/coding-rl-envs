# frozen_string_literal: true

module Api
  module V1
    class HealthController < ApplicationController
      
      # Reports healthy even when critical services are down

      skip_before_action :authenticate!

      def show
        checks = perform_health_checks

        
        # If 9/10 services healthy, still reports healthy
        all_healthy = checks.values.any? { |c| c[:status] == 'healthy' }

        if all_healthy
          render json: {
            status: 'healthy',
            timestamp: Time.current.iso8601,
            checks: checks
          }
        else
          render json: {
            status: 'unhealthy',
            timestamp: Time.current.iso8601,
            checks: checks
          }, status: :service_unavailable
        end
      end

      def ready
        
        render json: { status: 'ready' }
      end

      def live
        render json: { status: 'live' }
      end

      private

      def perform_health_checks
        checks = {}

        # Check Redis
        checks[:redis] = check_redis

        # Check PostgreSQL
        checks[:database] = check_database

        # Check downstream services
        
        ServiceRegistry::SERVICES.each do |service|
          checks[service.to_sym] = check_service(service)
        end

        checks
      end

      def check_redis
        Redis.current.ping
        { status: 'healthy', latency_ms: 0 }
      rescue StandardError => e
        
        # Load balancer won't route traffic away
        { status: 'degraded', error: e.message }
      end

      def check_database
        ActiveRecord::Base.connection.execute('SELECT 1')
        { status: 'healthy' }
      rescue StandardError => e
        
        { status: 'degraded', error: e.message }
      end

      def check_service(service_name)
        endpoint = ServiceRegistry.new.get_endpoint(service_name)
        
        # With 10 services, health check takes 50+ seconds
        response = HTTP.timeout(5).get("#{endpoint}/health")

        if response.status.success?
          { status: 'healthy' }
        else
          
          { status: 'degraded', http_status: response.status.to_i }
        end
      rescue StandardError => e
        { status: 'degraded', error: e.message }
      end
    end
  end
end

# Correct implementation:
# def show
#   checks = perform_health_checks
#
#   # Critical services that must be healthy
#   critical = [:redis, :database, :auth, :orders]
#   critical_healthy = critical.all? { |s| checks[s][:status] == 'healthy' }
#
#   # Overall health based on critical services
#   overall_status = critical_healthy ? 'healthy' : 'unhealthy'
#
#   status_code = overall_status == 'healthy' ? :ok : :service_unavailable
#
#   render json: {
#     status: overall_status,
#     timestamp: Time.current.iso8601,
#     checks: checks
#   }, status: status_code
# end
#
# def perform_health_checks
#   checks = {}
#
#   # Run checks in parallel with short timeout
#   threads = []
#
#   threads << Thread.new { checks[:redis] = check_redis }
#   threads << Thread.new { checks[:database] = check_database }
#
#   ServiceRegistry::SERVICES.each do |service|
#     threads << Thread.new { checks[service.to_sym] = check_service(service) }
#   end
#
#   # Wait with overall timeout
#   threads.each { |t| t.join(2) }
#
#   checks
# end
#
# def check_redis
#   start = Time.current
#   Redis.current.ping
#   { status: 'healthy', latency_ms: ((Time.current - start) * 1000).round }
# rescue StandardError => e
#   { status: 'unhealthy', error: e.message }  # unhealthy, not degraded
# end
