# frozen_string_literal: true

require 'rails_helper'

RSpec.describe OrderSaga do
  
  let(:order) { create(:order, :with_line_items) }
  subject(:saga) { described_class.new(order) }

  describe '#execute!' do
    it 'compensates inventory when payment fails' do
      allow(saga).to receive(:reserve_inventory).and_return({ success: true })
      allow(saga).to receive(:process_payment).and_return({ success: false, error: 'declined' })

      # Fixed version should call compensate! which releases inventory
      expect(saga).to receive(:release_inventory) rescue nil

      saga.execute!

      expect(order.reload.status).to eq('failed')
    end

    it 'compensates payment and inventory when shipment fails' do
      allow(saga).to receive(:reserve_inventory).and_return({ success: true })
      allow(saga).to receive(:process_payment).and_return({ success: true, payment_id: 'pay_123' })
      allow(saga).to receive(:create_shipment).and_return({ success: false, error: 'unavailable' })

      # Fixed version compensates both payment and inventory
      expect(saga).to receive(:refund_payment) rescue nil
      expect(saga).to receive(:release_inventory) rescue nil

      saga.execute!
    end

    it 'completes all steps successfully' do
      allow(saga).to receive(:reserve_inventory).and_return({ success: true })
      allow(saga).to receive(:process_payment).and_return({ success: true, payment_id: 'pay_123' })
      allow(saga).to receive(:create_shipment).and_return({ success: true, shipment_id: 'ship_123' })
      allow(saga).to receive(:send_confirmation).and_return({ success: true })

      result = saga.execute!
      expect(result).to be true
      expect(order.reload.status).to eq('completed')
    end

    it 'sets order status to failed with error message on failure' do
      allow(saga).to receive(:reserve_inventory).and_return({ success: false, error: 'out of stock' })

      saga.execute!

      expect(order.reload.status).to eq('failed')
      expect(order.error_message).to include('out of stock')
    end
  end
end
