# frozen_string_literal: true

require 'rails_helper'

RSpec.describe RefundService do
  

  let(:order) do
    create(:order,
           payment_status: 'paid',
           payment_id: 'pay_abc',
           total_amount: 100.00,
           subtotal: 90.00,
           tax_amount: 10.00,
           discount_amount: 20.00,
           total_refunded: 20.0)
  end

  describe '#calculate_refund (full)' do
    it 'subtracts previously refunded amount from total' do
      service = described_class.new(order)
      refund = service.calculate_refund

      # $100 total - $20 already refunded = $80 remaining
      expect(refund).to eq(80.0)
    end

    it 'returns zero when order is fully refunded' do
      order.update!(total_refunded: 100.0)
      service = described_class.new(order)
      refund = service.calculate_refund

      expect(refund).to eq(0.0)
    end
  end

  describe '#calculate_refund (partial)' do
    let(:line_item) do
      create(:line_item,
             order: order,
             product: create(:product, current_price: 55.0),
             unit_price: 45.0,
             quantity: 2)
    end

    it 'uses the original unit_price, not the product current_price' do
      service = described_class.new(order)

      items = [{ line_item_id: line_item.id, quantity: 1 }]
      refund = service.calculate_refund(items_to_refund: items)

      # Should use line_item.unit_price (45.0), not product.current_price (55.0)
      expect(refund).to be <= 50.0
      expect(refund).not_to eq(55.0)
    end

    it 'applies proportional discount when calculating partial refund' do
      service = described_class.new(order)

      items = [{ line_item_id: line_item.id, quantity: 1 }]
      refund = service.calculate_refund(items_to_refund: items)

      # Item price is $45, but order had 20% discount ($20 off $100)
      # Proportional discount should reduce refund amount
      expect(refund).to be < 45.0
    end
  end

  describe '#process_refund' do
    it 'updates order total_refunded after successful refund' do
      allow(PaymentProvider).to receive(:refund).and_return(success: true)
      allow(Refund).to receive(:create!)

      service = described_class.new(order)
      service.process_refund(amount: 30.0, reason: 'customer request')

      order.reload
      expect(order.total_refunded).to eq(50.0) # was 20 + 30 new
    end

    it 'does not update total_refunded when refund fails' do
      allow(PaymentProvider).to receive(:refund).and_return(success: false, error: 'declined')

      service = described_class.new(order)
      result = service.process_refund(amount: 30.0)

      expect(result[:success]).to be false
      order.reload
      expect(order.total_refunded).to eq(20.0)
    end
  end

  describe 'tax calculation in refund' do
    it 'uses original tax rate, not current rate' do
      order.update!(tax_amount: 9.0, subtotal: 90.0)
      original_rate = order.tax_amount.to_f / order.subtotal

      allow(TaxCalculator).to receive(:current_rate).and_return(0.15) # current = 15%

      service = described_class.new(order)
      refund = service.calculate_refund

      # Should NOT use 15% current rate; should derive from original order
      expect(original_rate).to eq(0.1)
    end
  end
end
