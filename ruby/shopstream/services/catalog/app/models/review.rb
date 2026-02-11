# frozen_string_literal: true

class Review < ApplicationRecord
  belongs_to :product

  validates :rating, presence: true, numericality: { in: 1..5 }
end
