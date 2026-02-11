# frozen_string_literal: true

class Product < ApplicationRecord
  has_many :stock_movements
  has_many :warehouse_locations
  has_many :warehouses, through: :warehouse_locations
  has_many :reservations

  validates :name, presence: true
  validates :sku, presence: true, uniqueness: true
end
