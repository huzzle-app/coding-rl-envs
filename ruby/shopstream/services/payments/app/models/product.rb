# frozen_string_literal: true

class Product < ApplicationRecord
  has_many :line_items

  validates :name, presence: true
  validates :sku, presence: true, uniqueness: true
  validates :price, presence: true, numericality: { greater_than_or_equal_to: 0 }

  scope :active, -> { where(active: true) }
  scope :in_stock, -> { where('stock > 0') }
end
