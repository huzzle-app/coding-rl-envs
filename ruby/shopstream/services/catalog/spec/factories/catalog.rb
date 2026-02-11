# frozen_string_literal: true

FactoryBot.define do
  factory :category do
    sequence(:name) { |n| "Category #{n}" }
    sequence(:slug) { |n| "category-#{n}" }
    parent { nil }

    trait :with_parent do
      association :parent, factory: :category
    end

    trait :with_children do
      after(:create) do |category|
        create_list(:category, 2, parent: category)
      end
    end

    trait :with_products do
      after(:create) do |category|
        create_list(:product, 3, category: category)
      end
    end
  end

  factory :brand do
    sequence(:name) { |n| "Brand #{n}" }
    sequence(:slug) { |n| "brand-#{n}" }
  end

  factory :product do
    sequence(:name) { |n| "Product #{n}" }
    sequence(:sku) { |n| "SKU-#{n}" }
    price { 29.99 }
    stock { 100 }
    active { true }
    view_count { 0 }
    purchase_count { 0 }
    association :category

    trait :with_brand do
      association :brand
    end

    trait :with_variants do
      after(:create) do |product|
        create_list(:variant, 2, product: product)
      end
    end

    trait :with_reviews do
      after(:create) do |product|
        create_list(:review, 3, product: product)
      end
    end

    trait :with_images do
      after(:create) do |product|
        create_list(:image, 2, imageable: product)
      end
    end

    trait :out_of_stock do
      stock { 0 }
    end

    trait :inactive do
      active { false }
    end
  end

  factory :variant do
    association :product
    sequence(:name) { |n| "Variant #{n}" }
    sequence(:sku) { |n| "VAR-#{n}" }
    price { 34.99 }
    stock { 50 }
  end

  factory :review do
    association :product
    user_id { rand(1..1000) }
    rating { rand(1..5) }
    content { "This is a review content" }
  end

  factory :image do
    url { "https://example.com/image.jpg" }
    association :imageable, factory: :product
  end
end
