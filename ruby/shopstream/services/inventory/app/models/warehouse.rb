# frozen_string_literal: true

class Warehouse < ApplicationRecord
  has_many :warehouse_locations
  has_many :products, through: :warehouse_locations
  has_many :stock_movements

  validates :name, presence: true
  validates :code, presence: true, uniqueness: true
end
