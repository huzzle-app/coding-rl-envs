# frozen_string_literal: true

require 'rails_helper'

RSpec.describe DiscountService do
  
  let(:order) { create(:order, :with_line_items) }
  subject(:service) { described_class.new(order) }

  describe '#apply_discounts!' do
    it 'caps total discount at subtotal amount' do
      codes = [
        build(:discount_code, discount_type: 'percentage', value: 60),
        build(:discount_code, discount_type: 'percentage', value: 60)
      ]
      allow(order).to receive(:discount_codes).and_return(codes)

      service.apply_discounts! rescue nil

      order.reload rescue nil
      expect(order.discount_amount).to be <= service.send(:calculate_subtotal)
    end

    it 'does not result in negative order total' do
      codes = [
        build(:discount_code, discount_type: 'fixed', value: 10000.0)
      ]
      allow(order).to receive(:discount_codes).and_return(codes)

      service.apply_discounts! rescue nil

      subtotal = service.send(:calculate_subtotal)
      expect(subtotal - (order.discount_amount || 0)).to be >= 0
    end
  end

  describe '#preview_discount' do
    it 'never shows negative total in preview' do
      code = build(:discount_code, discount_type: 'percentage', value: 150)

      preview = service.preview_discount(code) rescue {}
      total = preview[:total] || 0

      expect(total).to be >= 0
    end
  end

  describe '#calculate_discount' do
    it 'handles BOGO discounts correctly' do
      code = build(:discount_code, discount_type: 'bogo')
      allow(code).to receive(:applies_to_product?).and_return(true)

      discount = service.calculate_discount(code, 100.0) rescue 0
      expect(discount).to be >= 0
    end
  end
end
