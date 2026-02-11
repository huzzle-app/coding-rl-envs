# frozen_string_literal: true

FactoryBot.define do
  factory :order do
    user_id { rand(1..1000) }
    status { 'pending' }
    total_amount { 100.0 }
    subtotal { 90.0 }
    tax_amount { 10.0 }
    shipping_amount { 5.0 }
    discount_amount { 0.0 }
    payment_status { 'pending' }
    payment_id { nil }
    paid_at { nil }
    payment_error { nil }
    total_refunded { 0.0 }

    trait :paid do
      payment_status { 'paid' }
      payment_id { "pay_#{SecureRandom.hex(8)}" }
      paid_at { Time.current }
    end

    trait :with_line_items do
      after(:create) do |order|
        create_list(:line_item, 2, order: order)
      end
    end

    trait :refunded do
      payment_status { 'refunded' }
      total_refunded { 100.0 }
    end
  end

  factory :line_item do
    association :order
    association :product
    quantity { 1 }
    unit_price { 45.0 }
  end

  factory :product do
    sequence(:name) { |n| "Product #{n}" }
    sequence(:sku) { |n| "SKU-#{n}" }
    price { 29.99 }
    current_price { 29.99 }
    stock { 100 }
    active { true }
  end

  factory :transaction do
    association :order
    amount { 100.0 }
    status { 'completed' }
    transaction_type { 'payment' }
    sequence(:external_id) { |n| "ext_#{n}_#{SecureRandom.hex(8)}" }
    sequence(:idempotency_key) { |n| "idem_#{n}_#{SecureRandom.hex(8)}" }
    payment_method { 'card_123' }
    currency { 'USD' }

    trait :pending do
      status { 'pending' }
    end

    trait :failed do
      status { 'failed' }
    end

    trait :refund do
      transaction_type { 'refund' }
    end
  end

  factory :refund do
    association :order
    association :transaction
    amount { 50.0 }
    status { 'pending' }
    reason { 'customer request' }

    trait :processed do
      status { 'processed' }
      processed_at { Time.current }
      sequence(:external_id) { |n| "ref_#{n}_#{SecureRandom.hex(8)}" }
    end

    trait :failed do
      status { 'failed' }
    end
  end

  factory :payment_method do
    user_id { rand(1..1000) }
    method_type { 'card' }
    sequence(:token) { |n| "tok_#{n}_#{SecureRandom.hex(8)}" }
    last_four { '4242' }
    brand { 'Visa' }
    exp_month { 12 }
    exp_year { Date.current.year + 2 }
    default { false }

    trait :default do
      default { true }
    end

    trait :expired do
      exp_year { Date.current.year - 1 }
    end
  end

  factory :account do
    sequence(:name) { |n| "Account #{n}" }
    account_type { 'revenue' }
    balance { 1000.0 }
    currency { 'USD' }

    trait :zero_balance do
      balance { 0.0 }
    end

    trait :expense do
      account_type { 'expense' }
    end
  end

  factory :ledger_entry do
    association :account
    amount { 100.0 }
    balance_after { 1100.0 }
    entry_type { 'credit' }
    sequence(:reference) { |n| "ref_#{n}" }
    description { 'Payment received' }

    trait :debit do
      entry_type { 'debit' }
      amount { -100.0 }
      balance_after { 900.0 }
    end
  end
end
