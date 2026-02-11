# frozen_string_literal: true

class Transaction < ApplicationRecord
  belongs_to :order
  has_many :refunds

  validates :amount, presence: true, numericality: true
  validates :status, presence: true
  validates :transaction_type, presence: true
  validates :idempotency_key, uniqueness: true, allow_nil: true

  scope :completed, -> { where(status: 'completed') }
  scope :pending, -> { where(status: 'pending') }
  scope :failed, -> { where(status: 'failed') }
  scope :payments, -> { where(transaction_type: 'payment') }
  scope :refunds, -> { where(transaction_type: 'refund') }

  serialize :metadata, coder: JSON

  def completed?
    status == 'completed'
  end

  def complete!(external_id: nil)
    update!(
      status: 'completed',
      external_id: external_id
    )
  end

  def fail!(error: nil)
    update!(status: 'failed')
    order.update!(payment_error: error) if error
  end
end
