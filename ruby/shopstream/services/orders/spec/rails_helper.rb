require 'spec_helper'
ENV['RAILS_ENV'] ||= 'test'
require_relative '../config/environment'
abort("The Rails environment is running in production mode!") if Rails.env.production?
require 'rspec/rails'

# Load FactoryBot
require 'factory_bot_rails'

RSpec.configure do |config|
  config.fixture_path = Rails.root.join('spec/fixtures')
  config.use_transactional_fixtures = true
  config.infer_spec_type_from_file_location!
  config.filter_rails_from_backtrace!

  # Include FactoryBot methods
  config.include FactoryBot::Syntax::Methods

  # Define stub classes for missing dependencies
  config.before(:suite) do
    # Stub external services if not defined
    unless defined?(ShopStream::KafkaConsumer)
      module ShopStream
        class KafkaConsumer
          def initialize(**opts); end
          def start; end
          def stop; end
          def subscribe(topic, &block); end
        end

        class KafkaProducer
          def self.publish(topic, data); true; end
        end
      end
    end

    unless defined?(ShipmentService)
      class ShipmentService
        def self.create_shipment(order); true; end
      end
    end

    unless defined?(OrderMailer)
      class OrderMailer
        def self.confirmation(order, user); OpenStruct.new(deliver_now: true); end
        def self.shipped(order, user); OpenStruct.new(deliver_now: true); end
        def self.delivered(order, user); OpenStruct.new(deliver_now: true); end
        def self.cancelled(order, user); OpenStruct.new(deliver_now: true); end
      end
    end

    unless defined?(SmsService)
      class SmsService
        def self.send(**opts); true; end
      end
    end

    unless defined?(PushService)
      class PushService
        def self.send(**opts); true; end
      end
    end

    unless defined?(RefundService)
      class RefundService
        def initialize(order); @order = order; end
        def process_refund; true; end
      end
    end

    unless defined?(NotificationLog)
      class NotificationLog < ApplicationRecord
        self.table_name = 'notification_logs'
      end
    end

    unless defined?(HttpClient)
      class HttpClient
        def initialize(base_url); @base_url = base_url; end
        def get(path); OpenStruct.new(success?: true, body: '{}'); end
        def post(path, data); OpenStruct.new(success?: true, body: '{}'); end
        def delete(path, data = {}); OpenStruct.new(success?: true, body: '{}'); end
      end
    end
  end

  # Stub external service clients
  config.before(:each) do
    allow(ShopStream::KafkaProducer).to receive(:publish).and_return(true) if defined?(ShopStream::KafkaProducer)
    allow(InventoryClient).to receive(:release).and_return(true) if defined?(InventoryClient)
    allow(InventoryClient).to receive(:reserve).and_return(true) if defined?(InventoryClient)
    allow(ShipmentService).to receive(:create_shipment).and_return(true) if defined?(ShipmentService)
  end
end
