# frozen_string_literal: true

require 'rails_helper'

RSpec.describe ShopStream::EventProcessor do
  subject(:processor) { described_class.new }

  
  describe '#process' do
    let(:event) do
      {
        'type' => 'order.created',
        'data' => { 'order_id' => 1 },
        'metadata' => { 'event_id' => 'evt-123' }
      }
    end

    it 'processes each event exactly once' do
      call_count = 0
      processor.register('order.created') { |_| call_count += 1 }

      processor.process(event)
      processor.process(event)

      expect(call_count).to eq(1)
    end

    it 'handles concurrent duplicate events safely' do
      call_count = 0
      mutex = Mutex.new
      processor.register('order.created') do |_|
        mutex.synchronize { call_count += 1 }
        sleep 0.01
      end

      threads = 5.times.map do
        Thread.new { processor.process(event) rescue nil }
      end
      threads.each(&:join)

      # Should be exactly 1, not 5
      expect(call_count).to eq(1)
    end

    it 'processes different events independently' do
      processed_ids = []
      mutex = Mutex.new
      processor.register('order.created') do |e|
        mutex.synchronize { processed_ids << (e['metadata']['event_id'] rescue 'unknown') }
      end

      event1 = event.dup
      event2 = event.merge('metadata' => { 'event_id' => 'evt-456' })

      processor.process(event1)
      processor.process(event2)

      expect(processed_ids.size).to eq(2)
    end

    it 'does not lose events when handler raises an error' do
      processor.register('order.created') { |_| raise 'handler error' }

      expect { processor.process(event) }.to raise_error('handler error')
    end
  end
end
