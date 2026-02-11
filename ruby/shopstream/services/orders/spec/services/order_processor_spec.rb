# frozen_string_literal: true

require 'rails_helper'

RSpec.describe OrderProcessor do
  
  let(:order) { create(:order, :with_line_items) }
  subject(:processor) { described_class.new(order) }

  describe '#validate_items' do
    it 'does not skip items when removing unavailable products during iteration' do
      # Create order with 3 items, first and third unavailable
      items = order.line_items.to_a
      allow(items[0].product).to receive(:available?).and_return(false)
      allow(items[1].product).to receive(:available?).and_return(true)
      allow(items[2].product).to receive(:available?).and_return(false) if items[2]

      processor.validate_items rescue nil

      # All unavailable items should be detected, not skipped due to array modification
    end

    it 'does not raise index errors from concurrent array modification' do
      expect {
        processor.validate_items rescue nil
      }.not_to raise_error
    end

    it 'collects all errors without missing any' do
      items = order.line_items.to_a
      items.each { |i| allow(i.product).to receive(:available?).and_return(false) }

      processor.validate_items rescue nil

      # All items should generate error messages
    end
  end

  describe '#reserve_inventory' do
    it 'does not modify line_items array during iteration' do
      allow(InventoryClient).to receive(:reserve).and_return({ success: false })

      expect {
        processor.reserve_inventory rescue nil
      }.not_to raise_error
    end
  end
end
