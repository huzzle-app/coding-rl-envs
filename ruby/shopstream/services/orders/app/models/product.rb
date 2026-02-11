# frozen_string_literal: true

class Product < ApplicationRecord
  has_many :line_items
  has_many :images, as: :imageable

  validates :name, presence: true
  validates :sku, presence: true, uniqueness: true
  validates :price, numericality: { greater_than_or_equal_to: 0 }

  def primary_image
    images.first
  end
end
