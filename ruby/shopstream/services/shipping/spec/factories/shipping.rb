# frozen_string_literal: true

FactoryBot.define do
  factory :shipment do
    order_id { rand(1..1000) }
    association :carrier
    sequence(:tracking_number) { |n| "TRACK#{n}#{SecureRandom.hex(4).upcase}" }
    status { 'pending' }
    carrier_name { 'UPS' }
    weight { 2.5 }
    dimensions { '10x8x6' }
    shipping_address { '123 Main St, San Francisco, CA 94102' }

    trait :shipped do
      status { 'shipped' }
      shipped_at { Time.current }
      estimated_delivery_at { 3.days.from_now }
    end

    trait :in_transit do
      status { 'in_transit' }
      shipped_at { 1.day.ago }
      estimated_delivery_at { 2.days.from_now }
    end

    trait :delivered do
      status { 'delivered' }
      shipped_at { 3.days.ago }
      delivered_at { Time.current }
    end

    trait :without_tracking do
      tracking_number { nil }
      carrier { nil }
      carrier_name { nil }
    end
  end

  factory :carrier do
    sequence(:name) { |n| "Carrier #{n}" }
    sequence(:code) { |n| "CARRIER#{n}" }
    api_endpoint { 'https://api.carrier.com/v1' }
    api_key { SecureRandom.hex(16) }
    active { true }
    supported_services { ['ground', 'express', 'overnight'] }
    tracking_url_template { 'https://tracking.carrier.com/track?number={{tracking_number}}' }

    trait :ups do
      name { 'UPS' }
      code { 'UPS' }
      api_endpoint { 'https://api.ups.com/v1' }
    end

    trait :fedex do
      name { 'FedEx' }
      code { 'FEDEX' }
      api_endpoint { 'https://api.fedex.com/v1' }
    end

    trait :usps do
      name { 'USPS' }
      code { 'USPS' }
      api_endpoint { 'https://api.usps.com/v1' }
    end

    trait :inactive do
      active { false }
    end
  end

  factory :shipping_rate do
    association :carrier
    service_level { 'ground' }
    origin_zone { 'US-WEST' }
    destination_zone { 'US-EAST' }
    base_rate { 9.99 }
    per_lb_rate { 0.50 }
    fuel_surcharge_pct { 5.0 }
    min_days { 5 }
    max_days { 7 }
    active { true }

    trait :express do
      service_level { 'express' }
      base_rate { 19.99 }
      per_lb_rate { 1.00 }
      min_days { 2 }
      max_days { 3 }
    end

    trait :overnight do
      service_level { 'overnight' }
      base_rate { 39.99 }
      per_lb_rate { 2.00 }
      min_days { 1 }
      max_days { 1 }
    end

    trait :inactive do
      active { false }
    end
  end
end
