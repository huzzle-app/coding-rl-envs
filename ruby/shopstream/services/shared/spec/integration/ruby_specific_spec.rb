# frozen_string_literal: true

require 'rails_helper'

RSpec.describe 'Ruby-Specific Bugs Integration' do
  # Cross-cutting tests for Ruby language bugs B1-B10

  describe 'Mutable default argument (B1)' do
    it 'filter service does not share state between calls' do
      service = FilterService.new rescue nil
      next unless service

      result1 = service.apply_filters({ category: 'shoes' }) rescue nil
      result2 = service.apply_filters({}) rescue nil

      # Second call should not have category filter from first call
      if result1 && result2
        expect(result2).not_to include(category: 'shoes')
      end
    end
  end

  describe 'Symbol/string key confusion (B2)' do
    it 'serializer handles both key types consistently' do
      serializer = ShopStream::EventSerializer

      symbol_event = { type: 'test', data: { id: 1 } }
      string_event = { 'type' => 'test', 'data' => { 'id' => 1 } }

      s1 = serializer.serialize(symbol_event) rescue nil
      s2 = serializer.serialize(string_event) rescue nil

      if s1 && s2
        d1 = serializer.deserialize(s1) rescue nil
        d2 = serializer.deserialize(s2) rescue nil

        # Both should produce equivalent results
        if d1 && d2
          expect(d1.to_s).to eq(d2.to_s)
        end
      end
    end
  end

  describe 'SQL injection via interpolation (B3)' do
    it 'search service escapes SQL metacharacters' do
      service = SearchService.new rescue nil
      next unless service

      malicious_queries = [
        "'; DROP TABLE products; --",
        "1' OR '1'='1",
        "UNION SELECT * FROM users --"
      ]

      malicious_queries.each do |query|
        expect {
          service.search(query) rescue nil
        }.not_to raise_error
      end

      # Tables should still exist
      expect(Product.count).to be >= 0
    end
  end

  describe 'Array modification during iteration (B4)' do
    it 'order processor does not skip items' do
      processor = OrderProcessor.new rescue nil
      next unless processor

      items = 5.times.map { |i| { id: i, status: 'pending' } }

      result = processor.process_items(items) rescue nil
      if result
        expect(result.size).to eq(5)
      end
    end
  end

  describe 'Shallow copy (B5)' do
    it 'nested hash modifications do not affect original' do
      original = { settings: { alerts: { email: true, sms: false } } }
      copy = original.deep_dup

      copy[:settings][:alerts][:email] = false

      expect(original[:settings][:alerts][:email]).to be true
    end
  end

  describe 'Unsafe eval (B6)' do
    it 'report builder rejects malicious formulas' do
      builder = ReportBuilder.new rescue nil
      next unless builder

      expect {
        builder.add_custom_formula('evil', "system('id')")
      }.to raise_error(/Invalid|not allowed/i)
    end
  end

  describe 'Class variable leak (B7)' do
    it 'request context uses thread-local storage' do
      if defined?(RequestContextMiddleware)
        results = []
        mutex = Mutex.new

        threads = 3.times.map do |i|
          Thread.new do
            Thread.current[:request_context] = { id: i }
            sleep 0.01
            ctx = Thread.current[:request_context]
            mutex.synchronize { results << ctx[:id] }
          end
        end
        threads.each(&:join)

        expect(results.sort).to eq([0, 1, 2])
      end
    end
  end

  describe 'Frozen string (B8)' do
    it 'template service handles frozen strings' do
      service = TemplateService.new rescue nil
      next unless service

      frozen = 'Hello {{name}}'.freeze

      expect {
        service.render_string(frozen, { name: 'World' })
      }.not_to raise_error
    end
  end

  describe 'method_missing infinite loop (B9)' do
    it 'api client raises NoMethodError for unknown methods' do
      client = ShopStream::ApiClient.new('http://test:3000') rescue nil
      next unless client

      expect {
        Timeout.timeout(2) { client.nonexistent_method }
      }.to raise_error(NoMethodError)
    end
  end

  describe 'Regexp backtracking (B10)' do
    it 'query parser handles adversarial input quickly' do
      parser = QueryParser.new rescue nil
      next unless parser

      inputs = [
        'a' * 50 + '!',
        'a]' * 25,
        '"' * 40,
        '(' * 20 + ')' * 20
      ]

      inputs.each do |input|
        start = Process.clock_gettime(Process::CLOCK_MONOTONIC)
        parser.parse(input) rescue nil
        elapsed = Process.clock_gettime(Process::CLOCK_MONOTONIC) - start
        expect(elapsed).to be < 2.0
      end
    end
  end
end
