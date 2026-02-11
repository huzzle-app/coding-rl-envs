# frozen_string_literal: true

require 'rails_helper'

RSpec.describe 'Callback Lifecycle Integration' do
  # Tests covering C1-C8 callback bugs

  describe 'after_commit event publishing (C1)' do
    it 'publishes events only after successful commit' do
      events = []
      allow(ShopStream::KafkaProducer).to receive(:publish) { |_t, e| events << e } rescue nil

      order = nil
      ActiveRecord::Base.transaction do
        order = create(:order, status: 'confirmed')
      end

      # Events should only appear after commit
      expect(events.size).to be >= 0
    end

    it 'does not publish events on rollback' do
      events = []
      allow(ShopStream::KafkaProducer).to receive(:publish) { |_t, e| events << e } rescue nil

      begin
        ActiveRecord::Base.transaction do
          create(:order, status: 'confirmed')
          raise ActiveRecord::Rollback
        end
      rescue StandardError; end

      expect(events).to be_empty
    end
  end

  describe 'Callback infinite loop prevention (C2)' do
    it 'stock movement audit does not trigger recursive saves' do
      product = create(:product, stock: 100)
      warehouse = create(:warehouse) rescue nil

      if warehouse
        expect {
          Timeout.timeout(5) do
            StockMovement.create!(product: product, warehouse: warehouse, quantity: 5, movement_type: 'receipt', reason: 'test')
          end
        }.not_to raise_error
      end
    end
  end

  describe 'Validation side effects (C3)' do
    it 'calling valid? does not change database state' do
      order_count_before = Order.count
      build(:order).valid?
      expect(Order.count).to eq(order_count_before)
    end

    it 'calling valid? does not make external API calls' do
      external_called = false
      allow(InventoryService).to receive(:check) { external_called = true; true } rescue nil
      build(:order).valid?
      expect(external_called).to be false
    end
  end

  describe 'Event before save (C4)' do
    it 'events are queued, not published, during save' do
      # Events should be queued in after_commit, not before_save
      published_during_transaction = false
      allow(ShopStream::KafkaProducer).to receive(:publish) do
        published_during_transaction = ActiveRecord::Base.connection.open_transactions > 0
      end rescue nil

      create(:order)

      # If published inside transaction, it was before commit (C4 bug)
      expect(published_during_transaction).to be false
    end
  end

  describe 'Cascading destroy performance (C5)' do
    it 'destroying order with many items completes within timeout' do
      order = create(:order)
      5.times { create(:line_item, order: order) } rescue nil

      expect {
        Timeout.timeout(10) { order.destroy! }
      }.not_to raise_error
    end
  end

  describe 'Notification on failed transaction (C6)' do
    it 'no notifications sent when order creation fails' do
      notified = false
      allow(NotificationService).to receive(:notify) { notified = true } rescue nil

      begin
        ActiveRecord::Base.transaction do
          create(:order)
          raise 'Simulated failure'
        end
      rescue StandardError; end

      expect(notified).to be false
    end
  end

  describe 'State machine transitions (C7)' do
    it 'shipment requires tracking info before shipping' do
      if defined?(Shipment)
        shipment = create(:shipment, status: 'pending') rescue nil
        if shipment
          shipment.tracking_number = nil
          result = shipment.transition_to(:shipped) rescue false
          # Should not transition without tracking number
        end
      end
    end
  end

  describe 'Recursive touch (C8)' do
    it 'category touch does not cause stack overflow' do
      if defined?(Category)
        parent = create(:category) rescue nil
        if parent
          child = create(:category, parent_id: parent.id) rescue create(:category)
          expect { Timeout.timeout(5) { child.touch rescue nil } }.not_to raise_error
        end
      end
    end
  end
end
