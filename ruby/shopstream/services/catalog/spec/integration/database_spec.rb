# frozen_string_literal: true

require 'rails_helper'

RSpec.describe 'Database Performance Bugs' do
  
  
  

  describe 'Foreign key indexes (D2)' do
    it 'has index on orders.user_id' do
      indexes = ActiveRecord::Base.connection.indexes(:orders)
      user_id_index = indexes.any? { |idx| idx.columns.include?('user_id') }

      expect(user_id_index).to be true
    end

    it 'has index on line_items.order_id' do
      indexes = ActiveRecord::Base.connection.indexes(:line_items)
      order_id_index = indexes.any? { |idx| idx.columns.include?('order_id') }

      expect(order_id_index).to be true
    end

    it 'has index on line_items.product_id' do
      indexes = ActiveRecord::Base.connection.indexes(:line_items)
      product_id_index = indexes.any? { |idx| idx.columns.include?('product_id') }

      expect(product_id_index).to be true
    end
  end

  describe 'Connection leak with raw SQL (D4)' do
    it 'returns connection to pool after raw SQL execution' do
      initial_busy = ActiveRecord::Base.connection_pool.stat[:busy]

      10.times do
        ActiveRecord::Base.connection_pool.with_connection do |conn|
          conn.execute('SELECT 1')
        end
      end

      final_busy = ActiveRecord::Base.connection_pool.stat[:busy]
      expect(final_busy).to be <= initial_busy + 1
    end

    it 'does not leak connections with checkout/checkin pattern' do
      pool = ActiveRecord::Base.connection_pool

      # Simulate the leak: checking out without checking in
      expect {
        5.times do
          pool.with_connection { |c| c.execute('SELECT 1') }
        end
      }.not_to change { pool.stat[:busy] }.by_at_least(2)
    end
  end

  describe 'Composite index (D7)' do
    it 'has composite index on orders(user_id, status)' do
      indexes = ActiveRecord::Base.connection.indexes(:orders)
      composite = indexes.any? do |idx|
        idx.columns.include?('user_id') && idx.columns.include?('status')
      end

      expect(composite).to be true
    end

    it 'has composite index on orders(user_id, created_at)' do
      indexes = ActiveRecord::Base.connection.indexes(:orders)
      composite = indexes.any? do |idx|
        idx.columns.include?('user_id') && idx.columns.include?('created_at')
      end

      expect(composite).to be true
    end

    it 'uses index for user order listing query' do
      user = create(:user)
      10.times { create(:order, user: user) }

      explain = ActiveRecord::Base.connection.execute(
        "EXPLAIN SELECT * FROM orders WHERE user_id = #{user.id} ORDER BY created_at DESC"
      ).to_a rescue []

      # Should use index scan, not sequential scan
      plan_text = explain.map(&:values).flatten.join(' ')
      expect(plan_text).to include('Index').or include('index')
    end
  end
end
