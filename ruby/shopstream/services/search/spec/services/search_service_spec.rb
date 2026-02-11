# frozen_string_literal: true

require 'rails_helper'

RSpec.describe SearchService do
  subject(:service) { described_class.new }

  describe '#advanced_search' do
    
    context 'SQL injection prevention' do
      it 'does not allow SQL injection through name parameter' do
        malicious_input = "'; DROP TABLE products; --"

        expect {
          service.advanced_search(name: malicious_input)
        }.not_to raise_error

        # Products table should still exist
        expect(Product.count).to be >= 0
      end

      it 'does not allow SQL injection through category parameter' do
        malicious_input = "1 OR 1=1"

        results = service.advanced_search(category: malicious_input)

        # Should not return all products
        expect(results.count).not_to eq(Product.count)
      end

      it 'does not allow SQL injection through price_range parameter' do
        malicious_input = "0 OR 1=1; --"

        expect {
          service.advanced_search(price_range: malicious_input)
        }.not_to raise_error
      end

      it 'does not allow SQL injection through sort parameter' do
        malicious_input = "created_at; DROP TABLE products; --"

        expect {
          service.advanced_search(sort: malicious_input)
        }.not_to raise_error

        expect(Product.count).to be >= 0
      end

      it 'sanitizes LIKE wildcards in search input' do
        # Should not match everything
        results = service.advanced_search(name: '%')
        expect(results.count).not_to eq(Product.count)
      end

      it 'uses parameterized queries for all user input' do
        allow(ActiveRecord::Base.connection).to receive(:execute).and_call_original

        service.advanced_search(name: 'test', category: '1')

        # Verify parameterized queries are used (implementation check)
        expect(ActiveRecord::Base.connection).not_to have_received(:execute).with(/test'/)
      end
    end

    context 'with Elasticsearch fallback' do
      before do
        allow(service).to receive(:elasticsearch_search).and_return(nil)
      end

      it 'falls back to database search without SQL injection' do
        results = service.search_products("test'; DROP TABLE products;--")

        # Should not raise and should not drop table
        expect(Product.count).to be >= 0
      end
    end
  end

  describe '#search_with_facets' do
    
    it 'validates facet names against whitelist' do
      malicious_facet = "category_id; DROP TABLE products; --"

      expect {
        service.search_with_facets('test', facets: [malicious_facet])
      }.to raise_error(ArgumentError, /Invalid facet/)
    end

    it 'only allows predefined facet columns' do
      allowed_facets = %w[category_id brand_id status]

      allowed_facets.each do |facet|
        expect {
          service.search_with_facets('test', facets: [facet])
        }.not_to raise_error
      end
    end
  end
end
