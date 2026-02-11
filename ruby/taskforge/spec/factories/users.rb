# frozen_string_literal: true

FactoryBot.define do
  factory :user do
    name { Faker::Name.name }
    email { Faker::Internet.unique.email }
    password { 'password123' }
    password_confirmation { 'password123' }
    confirmed_at { Time.current }

    trait :admin do
      admin { true }
    end

    trait :unconfirmed do
      confirmed_at { nil }
    end

    trait :with_preferences do
      settings { { 'theme' => 'dark', 'notifications' => true } }
      notification_preferences { { 'task_assigned' => true, 'mentioned' => true } }
    end
  end
end
