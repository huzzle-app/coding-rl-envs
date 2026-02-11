# frozen_string_literal: true

class DiscountCode < ApplicationRecord
  validates :code, presence: true, uniqueness: true
  validates :discount_type, presence: true
  validates :value, presence: true, numericality: { greater_than: 0 }
end
