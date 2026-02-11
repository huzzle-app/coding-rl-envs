require_relative 'boot'
require 'rails'
require 'active_model/railtie'
require 'active_record/railtie'
require 'action_controller/railtie'
require 'action_view/railtie'
require 'active_job/railtie'

Bundler.require(*Rails.groups)

module Orders
  class Application < Rails::Application
    config.load_defaults 7.1
    config.api_only = true
    config.autoload_paths << Rails.root.join('shared/lib')
    config.eager_load_paths << Rails.root.join('shared/lib')
  end
end
