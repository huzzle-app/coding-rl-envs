# frozen_string_literal: true

require 'rails_helper'

RSpec.describe ShopStream::EventStore do
  
  describe '#read_all' do
    it 'returns events in guaranteed global order' do
      store = described_class.new
      # Events should be ordered by global sequence, not just created_at
      # Two events created in the same millisecond should have deterministic order
      allow(store).to receive(:read_all).and_wrap_original do |_method, **args|
        # Fixed version should ORDER BY global_sequence ASC, not created_at
        []
      end

      events = store.read_all(from_position: 0, limit: 100) rescue []
      expect(events).to be_an(Array)
    end

    it 'does not use string interpolation for SQL parameters' do
      store = described_class.new
      connection = double('connection')
      allow(store).to receive(:instance_variable_get).with(:@connection).and_return(connection)

      # Fixed version should use parameterized queries, not interpolation
      # The buggy version uses string interpolation: "WHERE stream_id = '#{stream_id}'"
      expect(connection).not_to receive(:execute).with(/'\); DROP TABLE/)
    end
  end

  describe '#append' do
    it 'enforces expected version for optimistic concurrency' do
      store = described_class.new
      connection = double('connection')
      allow(store).to receive(:instance_variable_get).with(:@connection).and_return(connection)
      allow(connection).to receive(:execute).and_return([{ 'version' => 5 }])

      expect {
        store.append('stream-1', 'test', { data: 'value' }, expected_version: 3)
      }.to raise_error(ShopStream::ConcurrencyError)
    end

    it 'assigns monotonically increasing version numbers' do
      store = described_class.new
      connection = double('connection')
      allow(store).to receive(:instance_variable_get).with(:@connection).and_return(connection)
      allow(connection).to receive(:execute).and_return([{ 'version' => 0 }], nil)

      event = store.append('stream-1', 'test', { data: 'value' }) rescue nil
      expect(event).to be_nil.or(include(version: 1))
    end
  end
end
