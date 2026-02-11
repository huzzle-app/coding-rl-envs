# frozen_string_literal: true

class LedgerEntry < ApplicationRecord
  belongs_to :account

  validates :amount, presence: true, numericality: true
  validates :balance_after, presence: true, numericality: true
  validates :entry_type, presence: true

  scope :credits, -> { where(entry_type: 'credit') }
  scope :debits, -> { where(entry_type: 'debit') }
  scope :by_reference, ->(ref) { where(reference: ref) }
end
