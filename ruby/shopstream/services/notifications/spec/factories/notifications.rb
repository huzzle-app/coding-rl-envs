# frozen_string_literal: true

FactoryBot.define do
  factory :notification do
    user_id { rand(1..1000) }
    notification_type { 'order_confirmation' }
    channel { 'email' }
    status { 'pending' }
    sequence(:recipient) { |n| "user#{n}@example.com" }
    subject { 'Order Confirmation' }
    body { 'Thank you for your order!' }
    metadata { { order_id: rand(1..1000) }.to_json }
    scheduled_at { nil }
    retry_count { 0 }

    trait :sent do
      status { 'sent' }
      sent_at { Time.current }
    end

    trait :delivered do
      status { 'delivered' }
      sent_at { 1.hour.ago }
      delivered_at { Time.current }
    end

    trait :read do
      status { 'read' }
      sent_at { 2.hours.ago }
      delivered_at { 1.hour.ago }
      read_at { Time.current }
    end

    trait :failed do
      status { 'failed' }
      error_message { 'Failed to deliver notification' }
      retry_count { 3 }
    end

    trait :scheduled do
      status { 'scheduled' }
      scheduled_at { 1.hour.from_now }
    end

    trait :sms do
      channel { 'sms' }
      recipient { '+15551234567' }
      subject { nil }
    end

    trait :push do
      channel { 'push' }
      recipient { 'device_token_123' }
    end
  end

  factory :notification_template do
    sequence(:name) { |n| "template-#{n}" }
    notification_type { 'order_confirmation' }
    channel { 'email' }
    subject_template { 'Order #{{order_id}} Confirmation' }
    body_template { 'Hello {{customer_name}}, your order #{{order_id}} has been confirmed. Total: ${{total}}' }
    default_variables { { company_name: 'ShopStream' }.to_json }
    active { true }

    trait :shipping_notification do
      name { 'shipping_notification' }
      notification_type { 'shipping_update' }
      subject_template { 'Your order has shipped!' }
      body_template { 'Hi {{customer_name}}, your order #{{order_id}} is on its way! Tracking: {{tracking_number}}' }
    end

    trait :sms do
      channel { 'sms' }
      subject_template { nil }
      body_template { 'ShopStream: Order #{{order_id}} confirmed. Total: ${{total}}' }
    end

    trait :inactive do
      active { false }
    end
  end
end
