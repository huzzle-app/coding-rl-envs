# frozen_string_literal: true

FactoryBot.define do
  factory :product do
    sequence(:name) { |n| "Product #{n}" }
    sequence(:sku) { |n| "SKU-#{n}" }
    price { 29.99 }
    stock { 100 }
    active { true }
    category_id { rand(1..10) }
    brand_id { rand(1..5) }

    trait :out_of_stock do
      stock { 0 }
    end

    trait :inactive do
      active { false }
    end
  end

  factory :search_query do
    query { 'laptop' }
    user_id { rand(1..1000) }
    ip_address { '127.0.0.1' }
    result_count { 25 }
    filters { { category: 'electronics' }.to_json }
    sort_by { 'relevance' }
    sort_order { 'desc' }
    page { 1 }
    per_page { 20 }
    response_time_ms { 45.5 }

    trait :empty_results do
      result_count { 0 }
    end

    trait :with_filters do
      filters { { category: 'electronics', price_range: '100-500', brand: 'Apple' }.to_json }
    end

    trait :slow do
      response_time_ms { 2500.0 }
    end

    trait :anonymous do
      user_id { nil }
    end
  end

  factory :search_index do
    sequence(:index_name) { |n| "products_#{n}" }
    document_type { 'product' }
    sequence(:document_id) { |n| n }
    content { 'Laptop computer with 16GB RAM and 512GB SSD' }
    metadata { { category: 'electronics', brand: 'Dell' }.to_json }
    boost { 1.0 }
    indexed_at { Time.current }

    trait :high_boost do
      boost { 2.0 }
    end

    trait :category_index do
      document_type { 'category' }
      content { 'Electronics and computers' }
    end

    trait :stale do
      indexed_at { 1.week.ago }
    end
  end
end
