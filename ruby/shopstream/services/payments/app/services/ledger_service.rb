# frozen_string_literal: true

class LedgerService
  
  # Read committed allows phantom reads, causing balance inconsistencies

  def initialize
    @connection = ActiveRecord::Base.connection
  end

  def record_transaction(account_id, amount, type:, reference:)
    
    # Concurrent transactions can see inconsistent data

    Account.transaction do
      account = Account.find(account_id)

      # Calculate new balance
      
      # reading the balance and writing the new entry
      new_balance = account.balance + amount

      LedgerEntry.create!(
        account_id: account_id,
        amount: amount,
        entry_type: type,
        reference: reference,
        balance_after: new_balance
      )

      account.update!(balance: new_balance)
    end
  end

  def transfer(from_account_id, to_account_id, amount)
    
    # Race condition can cause inconsistent state

    Account.transaction do
      from_account = Account.find(from_account_id)
      to_account = Account.find(to_account_id)

      raise 'Insufficient balance' if from_account.balance < amount

      
      from_account.balance -= amount
      to_account.balance += amount

      from_account.save!
      to_account.save!

      # Record ledger entries
      
      record_entries(from_account_id, to_account_id, amount)
    end
  end

  def calculate_balance(account_id)
    
    # due to concurrent modifications
    ledger_balance = LedgerEntry.where(account_id: account_id).sum(:amount)
    current_balance = Account.find(account_id).balance

    
    if ledger_balance != current_balance
      Rails.logger.error("Balance mismatch for account #{account_id}: " \
                         "ledger=#{ledger_balance}, current=#{current_balance}")
    end

    current_balance
  end

  private

  def record_entries(from_account_id, to_account_id, amount)
    reference = SecureRandom.uuid

    LedgerEntry.create!(
      account_id: from_account_id,
      amount: -amount,
      entry_type: 'transfer_out',
      reference: reference
    )

    LedgerEntry.create!(
      account_id: to_account_id,
      amount: amount,
      entry_type: 'transfer_in',
      reference: reference
    )
  end
end

# Correct implementation using SERIALIZABLE isolation:
# def record_transaction(account_id, amount, type:, reference:)
#   Account.transaction(isolation: :serializable) do
#     # Lock the account row
#     account = Account.lock.find(account_id)
#
#     new_balance = account.balance + amount
#
#     # Create entry and update balance atomically
#     LedgerEntry.create!(
#       account_id: account_id,
#       amount: amount,
#       entry_type: type,
#       reference: reference,
#       balance_after: new_balance
#     )
#
#     account.update!(balance: new_balance)
#   end
# rescue ActiveRecord::SerializationFailure
#   retry
# end
#
# def transfer(from_account_id, to_account_id, amount)
#   # Consistent lock ordering to prevent deadlock
#   account_ids = [from_account_id, to_account_id].sort
#
#   Account.transaction(isolation: :serializable) do
#     accounts = Account.where(id: account_ids).lock.order(:id).index_by(&:id)
#
#     from_account = accounts[from_account_id]
#     to_account = accounts[to_account_id]
#
#     raise 'Insufficient balance' if from_account.balance < amount
#
#     from_account.decrement!(:balance, amount)
#     to_account.increment!(:balance, amount)
#
#     record_entries(from_account_id, to_account_id, amount)
#   end
# end
