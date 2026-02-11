# frozen_string_literal: true

class OrderTransaction < ApplicationRecord
  belongs_to :order

  validates :amount, presence: true, numericality: { greater_than_or_equal_to: 0 }
  validates :status, presence: true
  validates :transaction_type, presence: true
end
