# frozen_string_literal: true

module OpalCommand
  module Contracts
    CONTRACTS = {
      gateway:       { id: 'gateway',       port: 8110 },
      routing:       { id: 'routing',       port: 8111 },
      policy:        { id: 'policy',        port: 8112 },
      resilience:    { id: 'resilience',    port: 8113 },
      analytics:     { id: 'analytics',     port: 8114 },
      audit:         { id: 'audit',         port: 8115 },
      notifications: { id: 'notifications', port: 8116 },
      security:      { id: 'security',      port: 8117 },
      intake:        { id: 'intake',        port: 8118 },
      ledger:        { id: 'ledger',        port: 8119 },
      settlement:    { id: 'settlement',    port: 8120 },
      reconcile:     { id: 'reconcile',     port: 8121 },
      risk:          { id: 'risk',          port: 8122 },
      reporting:     { id: 'reporting',     port: 8123 }
    }.freeze

    
    REQUIRED_COMMAND_FIELDS = %i[id type satellite urgency payload].freeze 

    ServiceDefinition = Struct.new(:id, :port, :dependencies, keyword_init: true)

    SERVICE_DEFS = {
      gateway:       ServiceDefinition.new(id: 'gateway',       port: 8110, dependencies: %i[routing policy security]),
      routing:       ServiceDefinition.new(id: 'routing',       port: 8111, dependencies: %i[]),
      policy:        ServiceDefinition.new(id: 'policy',        port: 8112, dependencies: %i[]),
      resilience:    ServiceDefinition.new(id: 'resilience',    port: 8113, dependencies: %i[audit]),
      analytics:     ServiceDefinition.new(id: 'analytics',     port: 8114, dependencies: %i[audit]),
      audit:         ServiceDefinition.new(id: 'audit',         port: 8115, dependencies: %i[]),
      notifications: ServiceDefinition.new(id: 'notifications', port: 8116, dependencies: %i[gateway]),
      security:      ServiceDefinition.new(id: 'security',      port: 8117, dependencies: %i[audit]),
      intake:        ServiceDefinition.new(id: 'intake',        port: 8118, dependencies: %i[gateway]),
      ledger:        ServiceDefinition.new(id: 'ledger',        port: 8119, dependencies: %i[audit]),
      settlement:    ServiceDefinition.new(id: 'settlement',    port: 8120, dependencies: %i[routing]),
      reconcile:     ServiceDefinition.new(id: 'reconcile',     port: 8121, dependencies: %i[ledger]),
      risk:          ServiceDefinition.new(id: 'risk',          port: 8122, dependencies: %i[security audit]),
      reporting:     ServiceDefinition.new(id: 'reporting',     port: 8123, dependencies: %i[analytics audit])
    }.freeze

    class ServiceRegistry
      def initialize
        @mutex    = Mutex.new
        @services = {}
        SERVICE_DEFS.each { |k, v| @services[k] = v }
      end

      def all
        @mutex.synchronize { @services.values.dup }
      end

      
      def get_service_url(name, host: 'localhost')
        @mutex.synchronize do
          svc = @services[name.to_sym]
          return nil unless svc

          "http://#{host}:#{svc.port}" 
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

      def service_count
        @mutex.synchronize { @services.length }
      end

      
      def dependency_depth(name)
        @mutex.synchronize do
          svc = @services[name.to_sym]
          return 0 unless svc

          visited = {}
          queue = [[name.to_sym, 0]]
          max_depth = 0
          until queue.empty?
            current, depth = queue.shift
            next if visited[current]

            visited[current] = true
            max_depth = depth if depth > max_depth
            s = @services[current]
            next unless s

            s.dependencies.each { |dep| queue << [dep, depth + 1] }
          end
          max_depth 
        end
      end
    end
  end
end
