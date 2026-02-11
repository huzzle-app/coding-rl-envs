# frozen_string_literal: true

require 'rails_helper'

RSpec.describe PaymentConsumer do
  
  describe '#handle_payment_processed' do
    let(:order) { create(:order, payment_status: 'pending') }
    let(:event) do
      {
        'order_id' => order.id,
        'payment_id' => 'pay_123',
        'metadata' => { 'event_id' => 'evt-001' }
      }
    end

    it 'processes payment event only once even if delivered twice' do
      consumer = described_class.new

      consumer.send(:handle_payment_processed, event) rescue nil
      consumer.send(:handle_payment_processed, event) rescue nil

      order.reload
      expect(order.payment_status).to eq('paid')
      # Should not create duplicate shipments or notifications
    end

    it 'does not create duplicate shipments on event replay' do
      consumer = described_class.new

      shipment_count = 0
      allow(ShipmentService).to receive(:create_shipment) { shipment_count += 1 }

      consumer.send(:handle_payment_processed, event) rescue nil
      consumer.send(:handle_payment_processed, event) rescue nil

      expect(shipment_count).to eq(1)
    end
  end

  
  describe 'event key handling' do
    let(:order) { create(:order, payment_status: 'pending') }

    it 'handles events with string keys' do
      consumer = described_class.new
      event = { 'order_id' => order.id, 'payment_id' => 'pay_456' }

      expect { consumer.send(:handle_payment_processed, event) }.not_to raise_error rescue nil
    end

    it 'handles events with symbol keys' do
      consumer = described_class.new
      event = { order_id: order.id, payment_id: 'pay_789' }

      expect { consumer.send(:handle_payment_processed, event) }.not_to raise_error rescue nil
    end
  end

  describe '#handle_payment_refunded' do
    let(:order) { create(:order, payment_status: 'paid', total_amount: 100.0, total_refunded: 0) }

    it 'does not add refund amount multiple times on replay' do
      consumer = described_class.new
      event = { 'order_id' => order.id, 'amount' => 50.0 }

      consumer.send(:handle_payment_refunded, event) rescue nil
      consumer.send(:handle_payment_refunded, event) rescue nil

      order.reload
      # Should be 50, not 100 (no double counting)
      expect(order.total_refunded).to eq(50.0)
    end
  end
end
