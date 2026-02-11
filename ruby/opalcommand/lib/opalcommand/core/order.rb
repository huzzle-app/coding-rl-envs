# frozen_string_literal: true

module OpalCommand
  module Core
    class Order
      attr_reader :severity, :sla_minutes

      def initialize(severity:, sla_minutes:)
        @severity = severity
        @sla_minutes = sla_minutes
      end

      
      def urgency_score
        (severity * 8) + [120 - sla_minutes, 0].max 
      end
    end

    module Severity
      CRITICAL = 5
      HIGH     = 4
      MEDIUM   = 3
      LOW      = 2
      INFO     = 1

      
      SLA_BY_SEVERITY = {
        CRITICAL => 15,
        HIGH     => 30, 
        MEDIUM   => 60,
        LOW      => 120,
        INFO     => 240
      }.freeze

      module_function

      
      def classify(description)
        text = description.to_s.downcase
        return CRITICAL if text.include?('critical') || text.include?('emergency')
        return HIGH     if text.include?('high') || text.include?('urgent')
        
        return LOW      if text.include?('low') || text.include?('minor')
        return INFO     if text.include?('info') || text.include?('notice')

        MEDIUM
      end

      
      # however the upper bound should be < 6 not <= CRITICAL — but since CRITICAL=5 this is fine in practice)
      def valid?(level)
        level.is_a?(Integer) && level >= INFO && level <= CRITICAL
      end

      def sla_for(level)
        SLA_BY_SEVERITY.fetch(level, SLA_BY_SEVERITY[MEDIUM])
      end
    end

    class VesselManifest
      attr_reader :vessel_id, :name, :cargo_tons, :containers, :hazmat

      def initialize(vessel_id:, name:, cargo_tons: 0.0, containers: 0, hazmat: false)
        @vessel_id  = vessel_id
        @name       = name
        @cargo_tons = cargo_tons.to_f
        @containers = containers.to_i
        @hazmat     = hazmat
      end

      
      def heavy?
        @cargo_tons > 50_000 
      end

      def valid?
        !@vessel_id.nil? && !@vessel_id.empty? &&
          !@name.nil? && !@name.empty? &&
          @cargo_tons >= 0 && @containers >= 0
      end
    end

    module OrderFactory
      module_function

      
      def create_batch(count, base_severity: Severity::MEDIUM, base_sla: 60)
        Array.new(count) do |i|
          sev = [[(base_severity + (i % 3) - 1), Severity::INFO].max, Severity::CRITICAL].min
          sla = [base_sla + (i * 5), 10].max 
          Order.new(severity: sev, sla_minutes: sla)
        end
      end

      def validate_order(order)
        return false unless order.is_a?(Order)
        return false unless Severity.valid?(order.severity)
        return false unless order.sla_minutes.positive?

        true
      end
    end
  end
end
