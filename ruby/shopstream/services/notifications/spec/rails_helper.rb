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
    unless defined?(EmailService)
      class EmailService
        def self.send(to:, subject:, body:); true; end
      end
    end

    unless defined?(SmsService)
      class SmsService
        def self.send(to:, message:); true; end
      end
    end

    unless defined?(PushService)
      class PushService
        def self.send(token:, title:, body:); true; end
      end
    end
  end
end
