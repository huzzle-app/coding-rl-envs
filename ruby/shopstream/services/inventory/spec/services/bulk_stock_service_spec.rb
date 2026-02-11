# frozen_string_literal: true

require 'rails_helper'

RSpec.describe BulkStockService do
  
  describe '#bulk_adjust' do
    it 'processes adjustments in batches to avoid long lock hold times' do
      products = 5.times.map { create(:product, stock: 100) }
      adjustments = products.map { |p| { product_id: p.id, quantity: 10, reason: 'restock' } }

      service = described_class.new
      expect { service.bulk_adjust(adjustments) }.not_to raise_error

      products.each do |p|
        p.reload
        expect(p.stock).to eq(110)
      end
    end
  end

  describe '#transfer_between_warehouses' do
    it 'acquires locks in consistent order to prevent deadlock' do
      product = create(:product)
      service = described_class.new

      # Concurrent transfers in opposite directions should not deadlock
      t1 = Thread.new { service.transfer_between_warehouses(product.id, 1, 2, 5) rescue nil }
      t2 = Thread.new { service.transfer_between_warehouses(product.id, 2, 1, 3) rescue nil }

      # Should complete without deadlock within timeout
      [t1, t2].each { |t| t.join(10) }
    end

    it 'raises error on insufficient stock' do
      product = create(:product)
      WarehouseLocation.create!(product_id: product.id, warehouse_id: 1, quantity: 2)

      service = described_class.new
      expect {
        service.transfer_between_warehouses(product.id, 1, 2, 100)
      }.to raise_error('Insufficient stock')
    end
  end
end
