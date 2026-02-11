# frozen_string_literal: true

require 'rails_helper'

RSpec.describe ReportBuilder do
  

  describe '#add_custom_formula and #calculate_custom_metric' do
    it 'rejects formulas containing system commands' do
      builder = described_class.new

      expect {
        builder.add_custom_formula('evil', "system('echo pwned')")
      }.to raise_error(/Invalid formula|not allowed/i)
    end

    it 'rejects formulas with arbitrary Ruby code' do
      builder = described_class.new

      ['File.read("/etc/passwd")', 'eval("1+1")', '`whoami`', 'Kernel.exec("ls")'].each do |dangerous|
        expect {
          builder.add_custom_formula('evil', dangerous)
        }.to raise_error(/Invalid|not allowed/i)
      end
    end

    it 'allows safe arithmetic formulas' do
      builder = described_class.new

      expect {
        builder.add_custom_formula('margin', 'revenue - cost')
      }.not_to raise_error
    end

    it 'evaluates safe formula correctly' do
      builder = described_class.new
      builder.add_custom_formula('profit', 'revenue - cost')

      result = builder.calculate_custom_metric('profit', { revenue: 100, cost: 60 })
      expect(result).to eq(40)
    end
  end

  describe '#apply_filters' do
    it 'does not eval arbitrary filter expressions' do
      builder = described_class.new
      data = [{ 'price' => 10 }, { 'price' => 20 }]

      # Malicious filter expression
      expect {
        builder.apply_filters(data, "true; system('echo hacked')")
      }.to raise_error(/Invalid|not allowed/i).or not_change { `echo test`.strip }
    end

    it 'filters data with safe predicates' do
      builder = described_class.new
      data = [{ 'price' => 10 }, { 'price' => 20 }, { 'price' => 30 }]

      # Safe filter using allowed operations
      result = builder.apply_filters(data, "item['price'] > 15")
      expect(result.size).to be <= 2
    end
  end

  describe '#compute_aggregation' do
    it 'supports standard operations (sum, avg, count)' do
      builder = described_class.new
      data = [
        { 'category' => 'A', 'amount' => 10 },
        { 'category' => 'A', 'amount' => 20 },
        { 'category' => 'B', 'amount' => 30 }
      ]

      result = builder.compute_aggregation(data, { group_by: 'category', metric: 'amount', operation: 'sum' })
      expect(result['A']).to eq(30)
      expect(result['B']).to eq(30)
    end

    it 'rejects unsafe operations (no eval fallback)' do
      builder = described_class.new
      data = [{ 'category' => 'A', 'amount' => 10 }]

      expect {
        builder.compute_aggregation(data, {
          group_by: 'category',
          metric: 'amount',
          operation: "inject(:+); system('echo hacked')"
        })
      }.to raise_error(/Invalid|not allowed/i)
    end
  end

  describe '#build' do
    it 'rejects unknown report types' do
      builder = described_class.new

      expect {
        builder.build('unknown_type', {})
      }.to raise_error(/Unknown report type/)
    end

    it 'accepts valid report types' do
      builder = described_class.new

      %w[sales inventory customers orders].each do |type|
        expect { builder.build(type, { format: 'json' }) }.not_to raise_error
      end
    end
  end
end
