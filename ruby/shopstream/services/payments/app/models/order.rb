# frozen_string_literal: true

class Order < ApplicationRecord
  has_many :line_items, dependent: :destroy
  has_many :transactions, dependent: :destroy
  has_many :refunds, dependent: :destroy

  validates :user_id, presence: true
  validates :status, presence: true
  validates :total_amount, numericality: { greater_than_or_equal_to: 0 }

  scope :pending_payment, -> { where(payment_status: 'pending') }
  scope :paid, -> { where(payment_status: 'paid') }
  scope :refunded, -> { where(payment_status: 'refunded') }

  def paid?
    payment_status == 'paid'
  end

  def can_refund?
    paid? && total_refunded < total_amount
  end

  def refundable_amount
    total_amount - total_refunded
  end

  def mark_as_paid!(payment_id:)
    update!(
      payment_status: 'paid',
      payment_id: payment_id,
      paid_at: Time.current
    )
  end

  def record_refund!(amount)
    new_total = total_refunded + amount
    update!(
      total_refunded: new_total,
      payment_status: new_total >= total_amount ? 'refunded' : 'partially_refunded'
    )
  end
end
