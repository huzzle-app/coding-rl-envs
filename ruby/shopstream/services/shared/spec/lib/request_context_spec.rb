# frozen_string_literal: true

require 'rails_helper'

RSpec.describe ShopStream::RequestContext do
  
  after { described_class.clear! }

  describe '.propagate_headers' do
    it 'returns headers hash with correlation ID' do
      described_class.correlation_id = 'test-corr-id'
      headers = described_class.propagate_headers

      expect(headers).to include('X-Correlation-ID' => 'test-corr-id')
    end

    it 'returns headers hash with user ID when present' do
      described_class.user_id = 42
      headers = described_class.propagate_headers

      expect(headers).to include('X-User-ID' => 42)
    end

    it 'omits nil values from headers' do
      described_class.correlation_id = nil
      described_class.user_id = nil
      headers = described_class.propagate_headers

      expect(headers).not_to have_key('X-Correlation-ID')
      expect(headers).not_to have_key('X-User-ID')
    end
  end

  describe '.with' do
    it 'scopes context to the block and restores afterward' do
      described_class.correlation_id = 'outer'

      described_class.with({ correlation_id: 'inner' }) do
        expect(described_class.correlation_id).to eq('inner')
      end

      expect(described_class.correlation_id).to eq('outer')
    end
  end

  describe 'thread isolation' do
    it 'maintains separate context per thread' do
      described_class.correlation_id = 'main-thread'

      thread_value = nil
      Thread.new do
        described_class.correlation_id = 'child-thread'
        thread_value = described_class.correlation_id
      end.join

      expect(described_class.correlation_id).to eq('main-thread')
      expect(thread_value).to eq('child-thread')
    end
  end
end
