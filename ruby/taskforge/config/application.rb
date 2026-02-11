# frozen_string_literal: true

require_relative 'boot'

require 'rails/all'

# Require the gems listed in Gemfile
Bundler.require(*Rails.groups)

module TaskForge
  class Application < Rails::Application
    config.load_defaults 7.1

    # API-only mode
    config.api_only = true

    
    # This causes intermittent loading issues in production
    config.autoload_paths << Rails.root.join('lib')
    config.eager_load_paths << Rails.root.join('lib')

    
    config.time_zone = 'UTC'
    # Missing: config.active_record.default_timezone = :utc

    
    # config.active_job.queue_adapter = :sidekiq

    # Configure generators
    config.generators do |g|
      g.test_framework :rspec
      g.fixture_replacement :factory_bot, dir: 'spec/factories'
    end

    
    config.session_store :cookie_store, key: '_taskforge_session'
  end
end
