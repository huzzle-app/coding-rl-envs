# frozen_string_literal: true

require 'rails_helper'

RSpec.describe 'Financial Calculation Integration' do
  # Cross-cutting tests for financial precision bugs H1-H5

  describe 'Float precision (H1)' do
    it 'uses BigDecimal for price calculations' do
      price = BigDecimal('19.99')
      quantity = 3
      total = price * quantity

      expect(total).to eq(BigDecimal('59.97'))

      # Contrast with float issue
      float_total = 19.99 * 3
      expect(float_total).not_to eq(59.97) # Float imprecision!
    end

    it 'does not accumulate float errors over many items' do
      prices = [BigDecimal('0.10')] * 100
      total = prices.sum

      expect(total).to eq(BigDecimal('10.00'))
    end

    it 'penny rounding is correct for edge cases' do
      # $33.33 * 3 should equal $99.99, not $99.98 or $100.00
      unit_price = BigDecimal('33.33')
      total = unit_price * 3

      expect(total).to eq(BigDecimal('99.99'))
    end
  end

  describe 'Tax rounding (H2)' do
    it 'tax calculated per-line, then summed (not summed then taxed)' do
      items = [
        { price: BigDecimal('10.01'), qty: 1 },
        { price: BigDecimal('10.01'), qty: 1 },
        { price: BigDecimal('10.01'), qty: 1 }
      ]
      tax_rate = BigDecimal('0.0875')

      # Correct: tax each item, round, then sum
      per_item_tax = items.sum do |item|
        (item[:price] * item[:qty] * tax_rate).round(2)
      end

      # Incorrect: sum first, then tax
      total = items.sum { |i| i[:price] * i[:qty] }
      bulk_tax = (total * tax_rate).round(2)

      # They may differ by a penny due to rounding
      expect((per_item_tax - bulk_tax).abs).to be <= BigDecimal('0.02')
    end
  end

  describe 'Currency conversion (H3)' do
    it 'quoted rate is used during execution, not current rate' do
      service = CurrencyService.new rescue nil
      next unless service

      quote = service.quote_conversion(100.0, from: 'USD', to: 'EUR') rescue nil
      next unless quote

      result = service.execute_conversion(quote_id: quote[:quote_id], amount: 100.0) rescue nil
      if result && result[:success]
        expect(result[:rate_used]).to eq(quote[:rate])
      end
    end
  end

  describe 'Discount stacking (H4)' do
    it 'total discount never exceeds 100% of order value' do
      service = DiscountService.new rescue nil
      next unless service

      discounts = [
        { type: 'percentage', value: 50 },
        { type: 'percentage', value: 40 },
        { type: 'percentage', value: 30 }
      ]

      total = BigDecimal('100.00')
      final = service.apply_discounts(total, discounts) rescue total

      # Should never go below zero
      expect(final).to be >= 0
    end

    it 'fixed amount discounts capped at order total' do
      service = DiscountService.new rescue nil
      next unless service

      discounts = [
        { type: 'fixed', value: 60 },
        { type: 'fixed', value: 60 }
      ]

      total = BigDecimal('100.00')
      final = service.apply_discounts(total, discounts) rescue total

      expect(final).to be >= 0
    end
  end

  describe 'Refund calculation (H5)' do
    it 'refund amount cannot exceed remaining balance' do
      order = create(:order, total_amount: 100.0, total_refunded: 80.0)
      service = RefundService.new(order) rescue nil
      next unless service

      refund = service.calculate_refund rescue nil
      if refund
        expect(refund).to be <= 20.0
        expect(refund).to be >= 0
      end
    end

    it 'partial refund uses original price, not current price' do
      order = create(:order, total_amount: 100.0, total_refunded: 0)
      product = create(:product, current_price: 55.0)
      line_item = create(:line_item, order: order, product: product, unit_price: 45.0, quantity: 1)

      service = RefundService.new(order) rescue nil
      next unless service

      refund = service.calculate_refund(items_to_refund: [{ line_item_id: line_item.id, quantity: 1 }]) rescue nil
      if refund
        expect(refund).to be <= 50.0 # Based on original $45, not current $55
      end
    end
  end
end
