# frozen_string_literal: true

module MercuryLedger
  module Contracts
    CONTRACTS = {
      gateway:       { id: 'gateway',       port: 8110 },
      routing:       { id: 'routing',       port: 8111 },
      policy:        { id: 'policy',        port: 8112 },
      resilience:    { id: 'resilience',    port: 8113 },
      analytics:     { id: 'analytics',     port: 8114 },
      audit:         { id: 'audit',         port: 8115 },
      notifications: { id: 'notifications', port: 8116 },
      security:      { id: 'security',      port: 8117 }
    }.freeze

    ServiceDefinition = Struct.new(:id, :port, :dependencies, keyword_init: true)

    
    REQUIRED_COMMAND_FIELDS = %w[service action priority].freeze

    SERVICE_DEFS = {
      gateway:       ServiceDefinition.new(id: 'gateway',       port: 8110, dependencies: %i[routing policy security]),
      routing:       ServiceDefinition.new(id: 'routing',       port: 8111, dependencies: %i[]),
      policy:        ServiceDefinition.new(id: 'policy',        port: 8112, dependencies: %i[]),
      resilience:    ServiceDefinition.new(id: 'resilience',    port: 8113, dependencies: %i[audit]),
      analytics:     ServiceDefinition.new(id: 'analytics',     port: 8114, dependencies: %i[audit]),
      audit:         ServiceDefinition.new(id: 'audit',         port: 8115, dependencies: %i[]),
      notifications: ServiceDefinition.new(id: 'notifications', port: 8116, dependencies: %i[gateway]),
      security:      ServiceDefinition.new(id: 'security',      port: 8117, dependencies: %i[audit])
    }.freeze

    class ServiceRegistry
      def initialize
        @mutex    = Mutex.new
        @services = {}
        SERVICE_DEFS.each { |k, v| @services[k] = v }
      end

      
      def dependency_depth(service_id)
        @mutex.synchronize do
          svc = @services[service_id.to_sym]
          return 0 unless svc

          max_depth = 0
          svc.dependencies.each do |dep|
            child_depth = dependency_depth_internal(dep)
            max_depth = child_depth if child_depth > max_depth
          end
          max_depth
        end
      end

      private

      def dependency_depth_internal(name)
        svc = @services[name.to_sym]
        return 0 unless svc
        return 0 if svc.dependencies.empty?

        svc.dependencies.map { |d| dependency_depth_internal(d) }.max + 1
      end

      public

      def all
        @mutex.synchronize { @services.values.dup }
      end

      
      def get_service_url(name, host: 'localhost')
        @mutex.synchronize do
          svc = @services[name.to_sym]
          return nil unless svc

          "https://#{host}:#{svc.port}"
        end
      end

      
      def validate_contract(name)
        @mutex.synchronize do
          svc = @services[name.to_sym]
          return false unless svc

          svc.dependencies.all? { |dep| @services.key?(dep) }
        end
      end

      
      def topological_order
        @mutex.synchronize do
          in_degree = {}
          adjacency = {}
          @services.each do |k, svc|
            in_degree[k] ||= 0
            adjacency[k] ||= []
            svc.dependencies.each do |dep|
              in_degree[dep] ||= 0
              adjacency[dep] ||= []
              adjacency[dep] << k
              in_degree[k] += 1
            end
          end

          queue = in_degree.select { |_, d| d.zero? }.keys.sort
          result = []
          until queue.empty?
            node = queue.shift
            result << node
            (adjacency[node] || []).each do |neighbor|
              in_degree[neighbor] -= 1
              queue << neighbor if in_degree[neighbor].zero?
            end
            queue.sort!
          end
          result
        end
      end
    end
  end
end
