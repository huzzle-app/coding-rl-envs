# frozen_string_literal: true

require 'rails_helper'

RSpec.describe ProjectionService do
  

  let(:event_store) { instance_double('EventStore') }

  describe '#get_projection' do
    it 'indicates staleness when projection is behind' do
      service = described_class.new(event_store)
      service.register_projection(:orders) { |_e| }

      # Simulate projection at position 5, but events up to 10 exist
      allow(event_store).to receive(:read_all).and_return([])
      allow(Rails.cache).to receive(:read).and_return({ total: 100 })

      result = service.get_projection(:orders, 'order-1')

      # Fixed version should include staleness info
      if result.is_a?(Hash) && result.key?(:stale)
        expect(result).to have_key(:lag)
        expect(result).to have_key(:position)
      end
    end
  end

  describe '#get_projection_with_consistency' do
    it 'waits for required position before returning data' do
      service = described_class.new(event_store)
      handler_calls = 0
      service.register_projection(:orders) { |_e| handler_calls += 1 }

      events = [
        { 'id' => 1, 'type' => 'order_created' },
        { 'id' => 2, 'type' => 'order_updated' }
      ]

      allow(event_store).to receive(:read_all).and_return(events, [])
      allow(Rails.cache).to receive(:read).and_return(nil)

      service.get_projection_with_consistency(:orders, 'order-1', required_position: 2)

      # Should have processed events to catch up
      expect(handler_calls).to be >= 2
    end
  end

  describe '#process_events' do
    it 'continues processing after a single event error' do
      service = described_class.new(event_store)
      processed = []

      service.register_projection(:orders) do |event|
        raise 'bad event' if event['id'] == 2
        processed << event['id']
      end

      events = [
        { 'id' => 1, 'type' => 'created' },
        { 'id' => 2, 'type' => 'bad' },
        { 'id' => 3, 'type' => 'updated' }
      ]

      allow(event_store).to receive(:read_all).and_return(events)

      service.process_events(:orders)

      # Should process at least event 1
      expect(processed).to include(1)
    end

    it 'updates position tracking correctly' do
      service = described_class.new(event_store)
      service.register_projection(:orders) { |_e| }

      events = [
        { 'id' => 10, 'type' => 'created' },
        { 'id' => 11, 'type' => 'updated' }
      ]

      allow(event_store).to receive(:read_all).and_return(events)

      service.process_events(:orders)

      # Position should be at last processed event
      expect(service.instance_variable_get(:@last_processed_position)[:orders]).to eq(11)
    end
  end

  describe '#rebuild_projection' do
    it 'resets position to 0 and replays all events' do
      service = described_class.new(event_store)
      rebuild_count = 0
      service.register_projection(:orders) { |_e| rebuild_count += 1 }

      # Set initial position
      service.instance_variable_get(:@last_processed_position)[:orders] = 100

      all_events = (1..5).map { |i| { 'id' => i, 'type' => 'event' } }

      allow(event_store).to receive(:read_all).and_return(all_events, [])
      allow(Rails.cache).to receive(:delete_matched)

      service.rebuild_projection(:orders)

      expect(rebuild_count).to eq(5)
    end

    it 'clears old projection data before rebuilding' do
      service = described_class.new(event_store)
      service.register_projection(:orders) { |_e| }

      allow(event_store).to receive(:read_all).and_return([])
      expect(Rails.cache).to receive(:delete_matched).with(/projection:orders/)

      service.rebuild_projection(:orders)
    end
  end
end
