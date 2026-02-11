# frozen_string_literal: true

class Brand < ApplicationRecord
  has_many :products

  validates :name, presence: true
end
