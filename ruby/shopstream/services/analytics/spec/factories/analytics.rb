# frozen_string_literal: true

FactoryBot.define do
  factory :order do
    user_id { rand(1..1000) }
    status { 'completed' }
    total_amount { rand(50..500).to_f }

    trait :pending do
      status { 'pending' }
    end

    trait :cancelled do
      status { 'cancelled' }
    end

    trait :recent do
      created_at { 1.day.ago }
    end

    trait :old do
      created_at { 6.months.ago }
    end
  end

  factory :event do
    event_type { 'page_view' }
    user_id { rand(1..1000) }
    entity_type { 'product' }
    entity_id { rand(1..100) }
    properties { { page: '/products/123', referrer: 'google' }.to_json }
    source { 'web' }
    sequence(:session_id) { |n| "session_#{n}_#{SecureRandom.hex(8)}" }
    ip_address { '127.0.0.1' }
    user_agent { 'Mozilla/5.0 (Test Browser)' }
    occurred_at { Time.current }

    trait :purchase do
      event_type { 'purchase' }
      properties { { order_id: rand(1..1000), amount: rand(50..500) }.to_json }
    end

    trait :add_to_cart do
      event_type { 'add_to_cart' }
      properties { { product_id: rand(1..100), quantity: rand(1..5) }.to_json }
    end

    trait :search do
      event_type { 'search' }
      entity_type { nil }
      entity_id { nil }
      properties { { query: 'laptop', results_count: 25 }.to_json }
    end

    trait :anonymous do
      user_id { nil }
    end

    trait :mobile do
      source { 'mobile_app' }
      user_agent { 'ShopStream/1.0 (iOS 15.0)' }
    end
  end

  factory :report do
    sequence(:name) { |n| "Report #{n}" }
    report_type { 'sales_summary' }
    status { 'pending' }
    parameters { { group_by: 'day' }.to_json }
    date_range { 1.month.ago.to_date..Date.current }
    output_path { '/tmp/reports/report.json' }
    output_format { 'json' }
    created_by_id { rand(1..100) }
    progress { 0 }

    trait :completed do
      status { 'completed' }
      progress { 100 }
      started_at { 1.hour.ago }
      completed_at { Time.current }
    end

    trait :in_progress do
      status { 'in_progress' }
      progress { 45 }
      started_at { 30.minutes.ago }
    end

    trait :failed do
      status { 'failed' }
      error_message { 'Report generation failed: timeout' }
      started_at { 2.hours.ago }
    end

    trait :customer_analytics do
      report_type { 'customer_analytics' }
    end

    trait :inventory_report do
      report_type { 'inventory' }
    end

    trait :csv_format do
      output_format { 'csv' }
      output_path { '/tmp/reports/report.csv' }
    end
  end
end
