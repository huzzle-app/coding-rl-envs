# frozen_string_literal: true

class Variant < ApplicationRecord
  belongs_to :product

  validates :name, presence: true
end
