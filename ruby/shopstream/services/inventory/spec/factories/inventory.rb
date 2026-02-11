# frozen_string_literal: true

FactoryBot.define do
  factory :product do
    sequence(:name) { |n| "Product #{n}" }
    sequence(:sku) { |n| "SKU-#{n}" }
    stock { 100 }
  end

  factory :warehouse do
    sequence(:name) { |n| "Warehouse #{n}" }
    sequence(:code) { |n| "WH-#{n}" }
    address { "123 Warehouse St" }
  end

  factory :warehouse_location do
    association :product
    association :warehouse
    quantity { 50 }
  end

  factory :stock_movement do
    association :product
    association :warehouse
    quantity { 10 }
    movement_type { "receipt" }
    reason { "Initial stock" }

    trait :receipt do
      movement_type { "receipt" }
      quantity { 10 }
    end

    trait :sale do
      movement_type { "sale" }
      quantity { -5 }
    end

    trait :adjustment do
      movement_type { "adjustment" }
      quantity { 0 }
    end

    trait :transfer do
      movement_type { "transfer" }
    end

    trait :damage do
      movement_type { "damage" }
      quantity { -2 }
    end

    trait :return do
      movement_type { "return" }
      quantity { 3 }
    end
  end

  factory :reservation do
    association :product
    order_id { rand(1..1000) }
    quantity { 5 }
    status { "pending" }
    expires_at { 15.minutes.from_now }

    trait :confirmed do
      status { "confirmed" }
    end

    trait :expired do
      status { "expired" }
      expires_at { 1.hour.ago }
    end

    trait :cancelled do
      status { "cancelled" }
    end
  end
end
