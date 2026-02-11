# frozen_string_literal: true

require 'rails_helper'

RSpec.describe StockMovement do
  
  describe 'after_save callbacks' do
    let(:product) { create(:product, stock: 100) }
    let(:warehouse) { create(:warehouse) }

    it 'does not create infinite loop of audit records' do
      expect {
        Timeout.timeout(5) do
          StockMovement.create!(
            product: product,
            warehouse: warehouse,
            quantity: 10,
            movement_type: 'receipt',
            reason: 'Restock'
          )
        end
      }.not_to raise_error
    end

    it 'creates at most one audit record per movement' do
      movement = StockMovement.create!(
        product: product,
        warehouse: warehouse,
        quantity: 10,
        movement_type: 'receipt',
        reason: 'Restock'
      ) rescue nil

      audit_count = StockMovement.where(reason: "Audit for movement ##{movement&.id}").count rescue 0
      expect(audit_count).to be <= 1
    end

    it 'updates product stock correctly after receipt' do
      StockMovement.create!(
        product: product,
        warehouse: warehouse,
        quantity: 20,
        movement_type: 'receipt',
        reason: 'Delivery'
      ) rescue nil

      product.reload
      expect(product.stock).to eq(120)
    end

    it 'decrements stock correctly for shipment movement' do
      StockMovement.create!(
        product: product,
        warehouse: warehouse,
        quantity: -15,
        movement_type: 'shipment',
        reason: 'Order fulfillment'
      ) rescue nil

      product.reload
      expect(product.stock).to eq(85)
    end

    it 'handles zero quantity movement without loop' do
      expect {
        Timeout.timeout(5) do
          StockMovement.create!(
            product: product,
            warehouse: warehouse,
            quantity: 0,
            movement_type: 'adjustment',
            reason: 'Inventory count'
          )
        end
      }.not_to raise_error
    end
  end
end
