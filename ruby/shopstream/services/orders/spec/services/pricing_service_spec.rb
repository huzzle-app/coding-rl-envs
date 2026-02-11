# frozen_string_literal: true

require 'rails_helper'

RSpec.describe PricingService do
  let(:order) { create(:order, :with_line_items) }
  subject(:service) { described_class.new(order) }

  describe '#calculate_total' do
    
    context 'thread safety' do
      it 'handles concurrent calculations safely' do
        threads = 10.times.map do
          Thread.new do
            described_class.new(order).calculate_subtotal
          end
        end

        results = threads.map(&:value)
        # All threads should get same result
        expect(results.uniq.size).to eq(1)
      end

      it 'does not corrupt memoized values across threads' do
        service1 = described_class.new(order)
        service2 = described_class.new(order)

        # Concurrent access to potentially shared state
        t1 = Thread.new { service1.calculate_total }
        t2 = Thread.new { service2.calculate_total }

        expect(t1.value).to eq(t2.value)
      end
    end

    
    context 'float precision in price calculation' do
      let(:line_items) do
        [
          build(:line_item, quantity: 1, unit_price: 19.99),
          build(:line_item, quantity: 1, unit_price: 5.99),
          build(:line_item, quantity: 1, unit_price: 3.99)
        ]
      end

      before do
        allow(order).to receive(:line_items).and_return(line_items)
        allow(order).to receive(:discount_codes).and_return([])
        allow(order).to receive(:shipping_method).and_return('standard')
      end

      it 'calculates subtotal without float precision errors' do
        subtotal = service.calculate_subtotal
        # 19.99 + 5.99 + 3.99 = 29.97 (exactly)
        expect(subtotal).to eq(29.97)
      end

      it 'handles many decimal place additions' do
        items = 100.times.map { build(:line_item, quantity: 1, unit_price: 0.01) }
        allow(order).to receive(:line_items).and_return(items)

        # Should be exactly 1.00, not 0.9999999999...
        expect(service.calculate_subtotal).to eq(1.00)
      end
    end
  end

  describe '#calculate_discount' do
    
    context 'when multiple discounts are applied' do
      let(:discount_codes) do
        [
          build(:discount_code, discount_type: 'percentage', value: 60),
          build(:discount_code, discount_type: 'percentage', value: 60)
        ]
      end

      before do
        allow(order).to receive(:discount_codes).and_return(discount_codes)
      end

      it 'caps total discount at 100%' do
        subtotal = 100.0
        discount = service.calculate_discount(subtotal)

        # Should not exceed subtotal
        expect(discount).to be <= subtotal
      end

      it 'does not result in negative total' do
        subtotal = service.calculate_subtotal
        discount = service.calculate_discount(subtotal)

        expect(subtotal - discount).to be >= 0
      end

      it 'limits discount stacking to 95% maximum' do
        subtotal = 100.0
        discount = service.calculate_discount(subtotal)

        expect(discount).to be <= 95.0
      end
    end
  end
end
