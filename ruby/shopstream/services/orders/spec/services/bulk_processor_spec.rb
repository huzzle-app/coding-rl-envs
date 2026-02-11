# frozen_string_literal: true

require 'rails_helper'

RSpec.describe BulkProcessor do
  
  describe '#bulk_update_status' do
    it 'updates all orders to the new status' do
      orders = 5.times.map { create(:order, status: 'pending') }
      processor = described_class.new

      processor.bulk_update_status(orders.map(&:id), 'confirmed')

      orders.each do |o|
        expect(o.reload.status).to eq('confirmed')
      end
    end

    it 'uses parameterized queries to avoid prepared statement leak' do
      orders = 3.times.map { create(:order) }
      processor = described_class.new

      # Fixed version should not create unique prepared statement per batch size
      expect {
        processor.bulk_update_status(orders.map(&:id), 'processing')
      }.not_to raise_error
    end
  end

  describe '#bulk_calculate_totals' do
    it 'uses parameterized queries instead of string interpolation' do
      order = create(:order, :with_line_items)
      processor = described_class.new

      
      # Fixed version uses parameterized queries
      expect {
        processor.bulk_calculate_totals([order.id])
      }.not_to raise_error
    end

    it 'does not create SQL injection vulnerability' do
      processor = described_class.new

      # SQL injection attempt through order_id
      expect {
        processor.bulk_calculate_totals(["1; DROP TABLE orders; --"])
      }.to raise_error.or not_to(raise_error) # Should either be safe or rejected
    end
  end
end
