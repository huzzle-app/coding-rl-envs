# frozen_string_literal: true

class Account < ApplicationRecord
  has_many :ledger_entries, dependent: :destroy

  validates :name, presence: true
  validates :account_type, presence: true
  validates :balance, numericality: true

  scope :revenue, -> { where(account_type: 'revenue') }
  scope :expense, -> { where(account_type: 'expense') }
  scope :liability, -> { where(account_type: 'liability') }

  def credit!(amount, reference: nil, description: nil)
    with_lock do
      new_balance = balance + amount
      ledger_entries.create!(
        amount: amount,
        balance_after: new_balance,
        entry_type: 'credit',
        reference: reference,
        description: description
      )
      update!(balance: new_balance)
    end
  end

  def debit!(amount, reference: nil, description: nil)
    with_lock do
      new_balance = balance - amount
      raise InsufficientFundsError if new_balance < 0

      ledger_entries.create!(
        amount: -amount,
        balance_after: new_balance,
        entry_type: 'debit',
        reference: reference,
        description: description
      )
      update!(balance: new_balance)
    end
  end

  class InsufficientFundsError < StandardError; end
end
