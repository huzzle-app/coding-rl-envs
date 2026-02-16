# frozen_string_literal: true

# Be sure to restart your server when you modify this file.

# Assuming you have not yet run the Devise install generator,
# here is a minimal configuration for an API-only application.

require 'devise/orm/active_record'

Devise.setup do |config|
  # The secret key used by Devise. Use `rails secret` to generate a new key.
  config.secret_key = ENV.fetch('DEVISE_SECRET_KEY') { Rails.application.secret_key_base }

  # Configure which authentication keys to use
  config.authentication_keys = [:email]

  # Configure case-insensitive keys
  config.case_insensitive_keys = [:email]

  # Configure which keys are stripped of whitespace
  config.strip_whitespace_keys = [:email]

  # Skip session storage for API-only apps
  config.skip_session_storage = [:http_auth, :params_auth]

  # Range for password length
  config.password_length = 8..128

  # Email regex used to validate email formats
  config.email_regexp = /\A[^@\s]+@[^@\s]+\z/

  # Time interval to timeout the user session without activity
  config.timeout_in = 30.minutes

  # Lock strategy and unlock keys
  config.lock_strategy = :failed_attempts
  config.unlock_keys = [:email]
  config.unlock_strategy = :both
  config.maximum_attempts = 5
  config.unlock_in = 1.hour

  # Reset password configuration
  config.reset_password_within = 6.hours

  # Sign out via :delete
  config.sign_out_via = :delete

  # When using JWT, we respond to navigational formats with JSON
  config.navigational_formats = []

  # Mailer sender address
  config.mailer_sender = 'noreply@taskforge.example.com'
end
