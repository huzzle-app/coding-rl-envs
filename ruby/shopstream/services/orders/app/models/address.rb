# frozen_string_literal: true

class Address < ApplicationRecord
  validates :street, presence: true
  validates :city, presence: true
  validates :state, presence: true
  validates :zip_code, presence: true
  validates :country, presence: true
end
