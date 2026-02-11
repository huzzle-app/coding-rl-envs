# frozen_string_literal: true

class Shipment < ApplicationRecord
  validates :carrier, presence: true
  validates :tracking_number, presence: true
  validates :status, presence: true
end
