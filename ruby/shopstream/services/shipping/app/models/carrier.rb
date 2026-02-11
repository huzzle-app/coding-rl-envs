# frozen_string_literal: true

class Carrier < ApplicationRecord
  has_many :shipments
  has_many :shipping_rates

  validates :name, presence: true
  validates :code, presence: true, uniqueness: true

  scope :active, -> { where(active: true) }

  serialize :supported_services, coder: JSON

  def active?
    active
  end

  def supports_service?(service)
    supported_services&.include?(service.to_s)
  end

  def tracking_url_for(tracking_number)
    tracking_url_template&.gsub('{{tracking_number}}', tracking_number)
  end

  def get_rate(origin:, destination:, service_level: 'ground')
    shipping_rates.find_by(
      origin_zone: origin,
      destination_zone: destination,
      service_level: service_level,
      active: true
    )
  end
end
