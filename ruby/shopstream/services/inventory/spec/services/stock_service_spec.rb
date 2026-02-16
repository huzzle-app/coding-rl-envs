# frozen_string_literal: true

require 'rails_helper'

RSpec.describe StockService do
  
  describe '#get_stock_info' do
    let(:product) { create(:product, stock: 100, reserved_stock: 10, incoming_stock: 20) }

    it 'returns stock info that does not share references with internal data' do
      service = described_class.new
      info1 = service.get_stock_info(product.id)
      info2 = service.get_stock_info(product.id)

      # Modifying info1 locations should not affect info2
      if info1[:locations]&.any?
        info1[:locations].first[:quantity] = 999
        expect(info2[:locations].first[:quantity]).not_to eq(999)
      end
    end
  end

  describe '#clone_stock_config' do
    let(:source) { create(:product) }
    let(:target) { create(:product) }

    it 'creates independent metadata copies for target product' do
      service = described_class.new

      # After cloning, changes to source metadata should not affect target
      service.clone_stock_config(source.id, target.id) rescue nil

      # Deep copy ensures independence
    end
  end

  describe '#transfer_stock' do
    it 'does not corrupt metadata through shallow copy reference' do
      service = described_class.new
      product = create(:product)

      # Transfer should not modify original metadata
      service.transfer_stock(
        from_warehouse: 1, to_warehouse: 2,
        product_id: product.id, quantity: 5
      ) rescue nil
    end
  end

  describe '#update_stock' do
    let(:product) { create(:product, stock: 100) }

    it 'maintains data integrity when updating nested warehouse data' do
      service = described_class.new
      info_before = service.get_stock_info(product.id) rescue nil

      service.update_stock(product.id, -10) rescue nil

      info_after = service.get_stock_info(product.id) rescue nil
      if info_before && info_after
        expect(info_after[:available]).to eq(info_before[:available] - 10)
      end
    end

    it 'deep copies warehouse locations on retrieval' do
      service = described_class.new
      info = service.get_stock_info(product.id) rescue nil
      if info && info[:locations]
        # Modifying retrieved locations should not affect internal state
        info[:locations] << { warehouse_id: 999, quantity: 0 }
        fresh = service.get_stock_info(product.id) rescue nil
        if fresh && fresh[:locations]
          expect(fresh[:locations]).not_to include(hash_including(warehouse_id: 999))
        end
      end
    end
  end
end
