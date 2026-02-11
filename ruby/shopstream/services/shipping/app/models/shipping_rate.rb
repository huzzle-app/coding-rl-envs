# frozen_string_literal: true

class ShippingRate < ApplicationRecord
  belongs_to :carrier

  validates :service_level, presence: true
  validates :base_rate, presence: true, numericality: { greater_than_or_equal_to: 0 }
  validates :service_level, uniqueness: { scope: [:carrier_id, :origin_zone, :destination_zone] }

  scope :active, -> { where(active: true) }
  scope :for_route, ->(origin, destination) { where(origin_zone: origin, destination_zone: destination) }
  scope :by_service, ->(level) { where(service_level: level) }

  def calculate_cost(weight)
    cost = base_rate + (weight * per_lb_rate)
    cost += cost * (fuel_surcharge_pct / 100)
    cost.round(2)
  end

  def estimated_delivery_range
    return nil unless min_days && max_days
    min_days == max_days ? "#{min_days} days" : "#{min_days}-#{max_days} days"
  end
end
