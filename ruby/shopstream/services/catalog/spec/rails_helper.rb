require 'spec_helper'
ENV['RAILS_ENV'] ||= 'test'
require_relative '../config/environment'
abort("The Rails environment is running in production mode!") if Rails.env.production?
require 'rspec/rails'
require 'factory_bot_rails'

RSpec.configure do |config|
  config.fixture_path = Rails.root.join('spec/fixtures')
  config.use_transactional_fixtures = true
  config.infer_spec_type_from_file_location!
  config.filter_rails_from_backtrace!
  config.include FactoryBot::Syntax::Methods

  config.before(:suite) do
    unless defined?(KafkaProducer)
      module ShopStream
        class KafkaProducer
          def self.publish(topic, data); true; end
        end
      end
      KafkaProducer = ShopStream::KafkaProducer
    end

    unless defined?(SearchIndexJob)
      class SearchIndexJob < ActiveJob::Base
        def perform(*args); end
      end
    end
  end

  config.before(:each) do
    allow(KafkaProducer).to receive(:publish).and_return(true) if defined?(KafkaProducer)
  end
end
