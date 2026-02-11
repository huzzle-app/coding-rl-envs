require 'spec_helper'
ENV['RAILS_ENV'] ||= 'test'
require_relative '../config/environment'
abort("The Rails environment is running in production mode!") if Rails.env.production?
require 'rspec/rails'

# Load FactoryBot
require 'factory_bot_rails'

# Load middleware files (naming doesn't match Rails conventions)
require_relative '../app/middleware/request_context'
require_relative '../app/middleware/timeout'
require_relative '../app/middleware/rate_limiter'

# Load lib files
require_relative '../lib/circuit_breaker'
require_relative '../lib/service_registry'

RSpec.configure do |config|
  config.fixture_path = Rails.root.join('spec/fixtures')
  config.use_transactional_fixtures = true
  config.infer_spec_type_from_file_location!
  config.filter_rails_from_backtrace!

  # Include FactoryBot methods
  config.include FactoryBot::Syntax::Methods

  # Define stub classes for missing dependencies
  config.before(:suite) do
    # Stub Redis if not available
    unless defined?(Redis)
      class Redis
        def initialize(**opts); @data = {}; end
        def get(key); @data[key]; end
        def set(key, value, **opts); @data[key] = value; end
        def setex(key, ttl, value); @data[key] = value; end
        def del(key); @data.delete(key); end
        def incr(key); @data[key] = (@data[key] || 0) + 1; end
        def expire(key, ttl); true; end
        def flushdb; @data = {}; end
        def multi; yield; end
        def exec; true; end
      end
    end
  end
end
