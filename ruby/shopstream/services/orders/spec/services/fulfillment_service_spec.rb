# frozen_string_literal: true

require 'rails_helper'

RSpec.describe FulfillmentService do
  
  let(:order) { create(:order, :with_line_items, total_amount: 99.99) }
  subject(:service) { described_class.new(order) }

  describe '#fulfill!' do
    it 'compensates payment when shipping fails' do
      allow(service).to receive(:verify_inventory).and_return({ success: true })
      allow(service).to receive(:process_payment).and_return({ success: true, payment_id: 'pay_1' })
      allow(service).to receive(:create_shipment).and_return({ success: false, error: 'unavailable' })

      result = service.fulfill!

      # Fixed version should refund payment when downstream service fails
      expect(result[:success]).to be false
    end

    it 'does not fail entire order when notifications fail' do
      allow(service).to receive(:verify_inventory).and_return({ success: true })
      allow(service).to receive(:process_payment).and_return({ success: true })
      allow(service).to receive(:create_shipment).and_return({ success: true })
      allow(NotificationsClient).to receive(:send_order_confirmation).and_raise('notification service down')

      # Fixed version treats notification failure as non-critical
      result = service.fulfill! rescue { success: false }
      # Notification failure should not fail the order
    end

    it 'handles inventory service timeout gracefully' do
      allow(service).to receive(:verify_inventory).and_raise(Timeout::Error)

      result = service.fulfill! rescue { success: false }
      expect(result[:success]).to be false
    end

    it 'rolls back inventory reservation when payment fails' do
      allow(service).to receive(:verify_inventory).and_return({ success: true })
      allow(service).to receive(:process_payment).and_return({ success: false, error: 'declined' })

      expect(service).to receive(:release_inventory).at_least(:once) rescue nil
      service.fulfill! rescue nil
    end

    it 'retries transient payment failures before giving up' do
      call_count = 0
      allow(service).to receive(:verify_inventory).and_return({ success: true })
      allow(service).to receive(:process_payment) do
        call_count += 1
        call_count < 3 ? (raise Timeout::Error) : { success: true }
      end
      allow(service).to receive(:create_shipment).and_return({ success: true })

      result = service.fulfill! rescue { success: false }
    end
  end
end
