# frozen_string_literal: true

FactoryBot.define do
  factory :service_endpoint do
    sequence(:service_name) { |n| "service-#{n}" }
    sequence(:url) { |n| "http://service-#{n}:3000" }
    status { 'healthy' }
    weight { 100 }
    last_health_check_at { Time.current }
    consecutive_failures { 0 }

    trait :unhealthy do
      status { 'unhealthy' }
      consecutive_failures { 3 }
    end

    trait :degraded do
      status { 'degraded' }
      consecutive_failures { 1 }
    end

    trait :low_weight do
      weight { 10 }
    end
  end

  factory :rate_limit_rule do
    sequence(:name) { |n| "rate-limit-#{n}" }
    key_type { 'ip' }
    limit { 100 }
    window_seconds { 60 }
    action { 'reject' }
    enabled { true }
    description { 'Default rate limit rule' }

    trait :by_user do
      key_type { 'user' }
    end

    trait :by_api_key do
      key_type { 'api_key' }
    end

    trait :disabled do
      enabled { false }
    end

    trait :throttle do
      action { 'throttle' }
    end

    trait :strict do
      limit { 10 }
      window_seconds { 60 }
    end

    trait :relaxed do
      limit { 1000 }
      window_seconds { 60 }
    end
  end
end
