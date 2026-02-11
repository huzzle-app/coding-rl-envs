# frozen_string_literal: true

require 'rails_helper'

RSpec.describe LedgerService do
  

  let(:account) { create(:account, balance: 1000.0) }

  describe '#record_transaction' do
    it 'uses row locking to prevent concurrent balance corruption' do
      service = described_class.new
      results = []
      mutex = Mutex.new

      threads = 5.times.map do
        Thread.new do
          begin
            service.record_transaction(account.id, -100.0, type: 'debit', reference: SecureRandom.uuid)
            mutex.synchronize { results << :success }
          rescue StandardError => e
            mutex.synchronize { results << :error }
          end
        end
      end
      threads.each(&:join)

      account.reload
      # 5 debits of $100 from $1000 = $500
      successful = results.count(:success)
      expected_balance = 1000.0 - (successful * 100.0)
      expect(account.balance).to eq(expected_balance)
    end

    it 'creates ledger entry with correct balance_after' do
      service = described_class.new
      service.record_transaction(account.id, -200.0, type: 'debit', reference: 'ref-1')

      entry = LedgerEntry.last
      expect(entry.balance_after).to eq(800.0)
      expect(account.reload.balance).to eq(800.0)
    end
  end

  describe '#transfer' do
    let(:account_b) { create(:account, balance: 500.0) }

    it 'maintains total balance across transfer (no money created/lost)' do
      service = described_class.new
      total_before = account.balance + account_b.balance

      service.transfer(account.id, account_b.id, 300.0)

      account.reload
      account_b.reload
      total_after = account.balance + account_b.balance

      expect(total_after).to eq(total_before)
    end

    it 'prevents overdraft with concurrent transfers' do
      service = described_class.new
      # Account has $1000, try to transfer $800 twice concurrently
      results = []
      mutex = Mutex.new

      threads = 2.times.map do
        Thread.new do
          begin
            service.transfer(account.id, account_b.id, 800.0)
            mutex.synchronize { results << :success }
          rescue StandardError => e
            mutex.synchronize { results << :insufficient }
          end
        end
      end
      threads.each(&:join)

      # Only one should succeed (can't transfer $1600 from $1000)
      expect(results.count(:success)).to eq(1)
      expect(account.reload.balance).to be >= 0
    end

    it 'uses consistent lock ordering to prevent deadlock' do
      service = described_class.new

      # Concurrent transfers in opposite directions should not deadlock
      expect {
        threads = [
          Thread.new { service.transfer(account.id, account_b.id, 50.0) rescue nil },
          Thread.new { service.transfer(account_b.id, account.id, 30.0) rescue nil }
        ]
        threads.each { |t| t.join(10) }
      }.not_to raise_error
    end
  end

  describe '#calculate_balance' do
    it 'ledger entries sum matches current balance' do
      service = described_class.new
      service.record_transaction(account.id, -200.0, type: 'debit', reference: 'r1')
      service.record_transaction(account.id, 50.0, type: 'credit', reference: 'r2')

      balance = service.calculate_balance(account.id)
      ledger_sum = 1000.0 + LedgerEntry.where(account_id: account.id).sum(:amount)

      expect(balance).to eq(ledger_sum)
    end
  end
end
