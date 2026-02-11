# frozen_string_literal: true

class Reservation < ApplicationRecord
  belongs_to :product

  validates :quantity, presence: true, numericality: { greater_than: 0 }
  validates :status, presence: true

  scope :pending, -> { where(status: 'pending') }
  scope :active, -> { where(status: ['pending', 'confirmed']) }
  scope :expired, -> { where('expires_at < ?', Time.current) }
end
