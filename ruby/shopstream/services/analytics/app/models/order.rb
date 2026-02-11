# frozen_string_literal: true

class Order < ApplicationRecord
  validates :user_id, presence: true
  validates :status, presence: true
  validates :total_amount, numericality: { greater_than_or_equal_to: 0 }

  scope :completed, -> { where(status: 'completed') }
  scope :pending, -> { where(status: 'pending') }
  scope :cancelled, -> { where(status: 'cancelled') }
  scope :in_date_range, ->(range) { where(created_at: range) }
  scope :for_user, ->(user_id) { where(user_id: user_id) }

  class << self
    def total_revenue(date_range = nil)
      scope = completed
      scope = scope.in_date_range(date_range) if date_range
      scope.sum(:total_amount)
    end

    def average_order_value(date_range = nil)
      scope = completed
      scope = scope.in_date_range(date_range) if date_range
      scope.average(:total_amount)&.round(2) || 0
    end

    def order_count_by_status(date_range = nil)
      scope = all
      scope = scope.in_date_range(date_range) if date_range
      scope.group(:status).count
    end
  end
end
