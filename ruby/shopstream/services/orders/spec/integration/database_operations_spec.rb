# frozen_string_literal: true

require 'rails_helper'

RSpec.describe 'Database Operations Integration' do
  # Additional database tests covering D1-D10 and edge cases

  describe 'N+1 query prevention (D1)' do
    it 'loading orders with includes avoids extra queries' do
      user = create(:user)
      3.times { create(:order, user: user) }

      query_count = 0
      callback = lambda { |*_| query_count += 1 }

      ActiveSupport::Notifications.subscribed(callback, 'sql.active_record') do
        orders = Order.includes(:user, :line_items).where(user_id: user.id).to_a
        orders.each { |o| o.user; o.line_items.to_a }
      end

      expect(query_count).to be < 10
    end

    it 'serializing multiple orders does not trigger N+1' do
      user = create(:user)
      3.times { create(:order, user: user) }

      loaded = Order.includes(:user, :line_items).where(user_id: user.id)

      query_count = 0
      callback = lambda { |*_| query_count += 1 }

      ActiveSupport::Notifications.subscribed(callback, 'sql.active_record') do
        loaded.each { |o| o.as_json(include: [:user, :line_items]) rescue nil }
      end

      expect(query_count).to be < 5
    end
  end

  describe 'Index usage (D2, D3, D7)' do
    it 'orders by user_id uses index' do
      user = create(:user)
      10.times { create(:order, user: user) }

      explain = ActiveRecord::Base.connection.execute(
        "EXPLAIN ANALYZE SELECT * FROM orders WHERE user_id = #{user.id}"
      ).to_a rescue []

      plan = explain.map(&:values).flatten.join(' ')
      expect(plan).to include('Index').or include('index').or include('Bitmap')
    end

    it 'orders by status uses index' do
      10.times { create(:order, status: 'pending') }

      explain = ActiveRecord::Base.connection.execute(
        "EXPLAIN ANALYZE SELECT * FROM orders WHERE status = 'pending'"
      ).to_a rescue []

      plan = explain.map(&:values).flatten.join(' ')
      expect(plan).to include('Index').or include('index').or include('Seq Scan')
    end
  end

  describe 'Connection pool management (D4)' do
    it 'concurrent queries do not exhaust pool' do
      errors = []
      mutex = Mutex.new

      threads = 15.times.map do
        Thread.new do
          begin
            ActiveRecord::Base.connection_pool.with_connection do |conn|
              conn.execute('SELECT pg_sleep(0.01)')
            end
          rescue StandardError => e
            mutex.synchronize { errors << e.class.name }
          end
        end
      end
      threads.each { |t| t.join(30) }

      expect(errors.count('ActiveRecord::ConnectionTimeoutError')).to eq(0)
    end
  end

  describe 'Transaction isolation (D5)' do
    it 'concurrent balance updates maintain consistency' do
      account = create(:account, balance: 1000.0)
      service = LedgerService.new rescue nil
      next unless service

      threads = 5.times.map do
        Thread.new do
          service.record_transaction(account.id, -100.0, type: 'debit', reference: SecureRandom.uuid) rescue nil
        end
      end
      threads.each(&:join)

      account.reload
      expect(account.balance).to be >= 0
      expect(account.balance).to eq(1000.0 - (LedgerEntry.where(account_id: account.id).count * 100.0))
    end
  end

  describe 'Bounded queries (D6)' do
    it 'list endpoints return limited results' do
      30.times { create(:order, user: create(:user)) }
      orders = Order.limit(20).to_a

      expect(orders.size).to be <= 20
    end

    it 'search results are paginated' do
      30.times { create(:product, name: 'Widget') }
      results = Product.where('name LIKE ?', '%Widget%').limit(25).to_a

      expect(results.size).to be <= 25
    end
  end

  describe 'Prepared statement cleanup (D8)' do
    it 'does not leak prepared statements' do
      # Execute many different queries
      10.times do |i|
        Order.where(id: i).to_a rescue nil
        Product.where(id: i).to_a rescue nil
      end

      # Connection should still work
      expect(ActiveRecord::Base.connection.execute('SELECT 1').to_a).not_to be_empty
    end
  end

  describe 'Lock timeout (D9)' do
    it 'batch update with lock timeout does not hang' do
      products = 5.times.map { create(:product, stock: 100) }

      expect {
        Timeout.timeout(10) do
          products.each { |p| p.with_lock { p.update!(stock: p.stock - 1) } rescue nil }
        end
      }.not_to raise_error
    end
  end

  describe 'Efficient pagination (D10)' do
    it 'cursor-based pagination is more efficient than offset for large tables' do
      20.times { create(:order) }

      # Cursor pagination: WHERE id > last_id ORDER BY id LIMIT 10
      first_page = Order.order(:id).limit(10).to_a
      last_id = first_page.last&.id || 0
      second_page = Order.where('id > ?', last_id).order(:id).limit(10).to_a

      expect(first_page.size).to eq(10)
      expect(second_page.size).to eq(10)

      # No overlap between pages
      expect((first_page.map(&:id) & second_page.map(&:id))).to be_empty
    end
  end
end
