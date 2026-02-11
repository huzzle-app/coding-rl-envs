# frozen_string_literal: true

require 'rails_helper'

RSpec.describe EventReplayService do
  
  let(:product) { create(:product, stock: 0, reserved_stock: 0, total_sold: 0) }

  describe '#rebuild_state' do
    it 'produces correct stock after replaying all events' do
      events = [
        { 'event_type' => 'stock_received', 'data' => { 'quantity' => 100 }.to_json },
        { 'event_type' => 'stock_sold', 'data' => { 'quantity' => 30 }.to_json },
        { 'event_type' => 'stock_received', 'data' => { 'quantity' => 50 }.to_json }
      ]

      allow(EventStore).to receive(:read).and_return(events)

      service = described_class.new(product.id)
      service.rebuild_state rescue nil

      product.reload
      # Expected: 0 + 100 - 30 + 50 = 120
      expect(product.stock).to eq(120)
    end

    it 'does not double-count events on repeated replay' do
      events = [
        { 'event_type' => 'stock_received', 'data' => { 'quantity' => 50 }.to_json }
      ]

      allow(EventStore).to receive(:read).and_return(events)

      service = described_class.new(product.id)
      service.rebuild_state rescue nil
      service.rebuild_state rescue nil

      product.reload
      # Should be 50, not 100 (no double-counting)
      expect(product.stock).to eq(50)
    end

    it 'handles stock_adjusted events idempotently' do
      events = [
        { 'event_type' => 'stock_received', 'data' => { 'quantity' => 100 }.to_json },
        { 'event_type' => 'stock_adjusted', 'data' => { 'adjustment' => -10 }.to_json }
      ]

      allow(EventStore).to receive(:read).and_return(events)

      service = described_class.new(product.id)
      service.rebuild_state rescue nil

      product.reload
      expect(product.stock).to eq(90)
    end
  end
end
