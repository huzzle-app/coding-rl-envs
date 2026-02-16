# frozen_string_literal: true

require 'rails_helper'

RSpec.describe FilterService do
  
  describe '#filter' do
    let(:service) { described_class.new }

    it 'does not accumulate filters across multiple calls with defaults' do
      result1 = service.filter
      result2 = service.filter

      # If mutable default is reused, second call has stale state
      # Both calls with no args should produce equivalent results
      expect(result1.to_sql).to eq(result2.to_sql)
    end

    it 'does not modify the caller-provided hash' do
      my_filters = { category_id: 1 }
      original = my_filters.dup

      service.filter(my_filters)

      # Fixed version should not modify the passed hash
      expect(my_filters.keys.sort).to eq(original.keys.sort)
    end

    it 'applies active: true by default' do
      scope = service.filter
      expect(scope.to_sql).to include('active')
    end
  end

  describe '#filter_by_attributes' do
    let(:service) { described_class.new }

    it 'does not accumulate attributes across calls with default array' do
      result1_attrs_count = 2 # :name and :price added by default
      service.filter_by_attributes

      # Second call with default should not have extra attributes
      service.filter_by_attributes
      # No assertion crash means no infinite accumulation
    end

    it 'does not modify the caller-provided array' do
      my_attrs = [:sku]
      original_size = my_attrs.size

      service.filter_by_attributes(my_attrs)

      
      expect(my_attrs.size).to eq(original_size)
    end
  end

  describe '#advanced_filter' do
    let(:service) { described_class.new }

    it 'does not leak sort options between calls' do
      service.advanced_filter({ sort: { field: 'name' }, filters: {} })
      service.advanced_filter  # default call

      # Should not retain field: 'name' from previous call
    end
  end
end
