# frozen_string_literal: true

class Refund < ApplicationRecord
  belongs_to :order
  belongs_to :transaction, optional: true

  validates :amount, presence: true, numericality: { greater_than: 0 }
  validates :status, presence: true

  scope :pending, -> { where(status: 'pending') }
  scope :processed, -> { where(status: 'processed') }
  scope :failed, -> { where(status: 'failed') }

  def process!
    update!(
      status: 'processed',
      processed_at: Time.current
    )
    order.record_refund!(amount)
  end

  def fail!(error: nil)
    update!(status: 'failed')
  end
end
