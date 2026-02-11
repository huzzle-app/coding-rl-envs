# frozen_string_literal: true

FactoryBot.define do
  factory :user do
    sequence(:email) { |n| "user#{n}@example.com" }
    full_name { 'Test User' }
    password_digest { 'hashed_password' }
    phone { '555-0100' }
    active { true }
    failed_login_attempts { 0 }
    locked_until { nil }

    trait :inactive do
      active { false }
    end

    trait :locked do
      locked_until { 1.hour.from_now }
      failed_login_attempts { 5 }
    end

    trait :with_sessions do
      after(:create) do |user|
        create_list(:session, 2, user: user)
      end
    end

    trait :with_api_keys do
      after(:create) do |user|
        create_list(:api_key, 2, user: user)
      end
    end
  end

  factory :session do
    association :user
    sequence(:session_token) { |n| "session_token_#{n}_#{SecureRandom.hex(16)}" }
    ip_address { '127.0.0.1' }
    user_agent { 'Mozilla/5.0 (Test Browser)' }
    expires_at { 24.hours.from_now }
    last_accessed_at { Time.current }

    trait :expired do
      expires_at { 1.hour.ago }
    end

    trait :expiring_soon do
      expires_at { 5.minutes.from_now }
    end
  end

  factory :api_key do
    association :user
    sequence(:name) { |n| "api-key-#{n}" }
    sequence(:key_hash) { |n| Digest::SHA256.hexdigest("key_#{n}_#{SecureRandom.hex(16)}") }
    sequence(:key_prefix) { |n| "sk_#{n}" }
    permissions { ['read', 'write'] }
    active { true }
    expires_at { 1.year.from_now }

    trait :read_only do
      permissions { ['read'] }
    end

    trait :expired do
      expires_at { 1.day.ago }
    end

    trait :inactive do
      active { false }
    end
  end
end
