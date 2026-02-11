# frozen_string_literal: true

FactoryBot.define do
  factory :order do
    association :user
    status { 'pending' }
    total_amount { 100.0 }
    tax_amount { 8.0 }
    shipping_amount { 5.0 }
    discount_amount { 0.0 }
    tax_rate { 0.08 }
    shipment_id { nil }
    payment_status { 'pending' }
    payment_id { nil }
    paid_at { nil }
    payment_error { nil }
    total_refunded { 0.0 }

    trait :with_line_items do
      after(:create) do |order|
        create_list(:line_item, 3, order: order)
      end
    end

    trait :with_user do
      # user is already associated by default
    end

    trait :with_address do
      association :shipping_address, factory: :address
    end

    trait :confirmed do
      status { 'confirmed' }
    end

    trait :shipped do
      status { 'shipped' }
    end
  end

  factory :user do
    sequence(:email) { |n| "user#{n}@example.com" }
    full_name { 'Test User' }
    password_digest { 'hashed_password' }
  end

  factory :address do
    street { '123 Main St' }
    city { 'San Francisco' }
    state { 'CA' }
    zip_code { '94102' }
    country { 'US' }
  end

  factory :line_item do
    association :order
    association :product
    quantity { 1 }
    unit_price { 29.99 }
  end

  factory :product do
    sequence(:name) { |n| "Product #{n}" }
    sequence(:sku) { |n| "SKU-#{n}" }
    price { 29.99 }
    stock { 100 }
    active { true }
    view_count { 0 }
    purchase_count { 0 }

    trait :with_images do
      after(:create) do |product|
        create(:image, imageable: product)
      end
    end
  end

  factory :image do
    url { 'https://example.com/image.jpg' }
    association :imageable, factory: :product
  end

  factory :category do
    sequence(:name) { |n| "Category #{n}" }
  end

  factory :order_transaction, class: 'OrderTransaction' do
    association :order
    amount { 100.0 }
    status { 'completed' }
    transaction_type { 'payment' }
  end

  factory :shipment do
    carrier { 'UPS' }
    tracking_number { 'TRACK123456' }
    status { 'in_transit' }
  end

  factory :discount_code do
    sequence(:code) { |n| "DISCOUNT#{n}" }
    discount_type { 'percentage' }
    value { 10 }
    active { true }
  end
end
