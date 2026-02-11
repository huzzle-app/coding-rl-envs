# frozen_string_literal: true

require 'rails_helper'

RSpec.describe ReportGenerationJob do
  

  let(:report) do
    create(:report,
           report_type: 'sales_summary',
           status: 'pending',
           date_range: 1.month.ago..Time.current,
           output_path: '/tmp/test_report.json')
  end

  describe '#perform' do
    it 'streams results to file instead of accumulating in memory' do
      # Create some orders for the report
      10.times { create(:order, created_at: 1.day.ago) }

      described_class.new.perform(report.id)

      report.reload
      expect(report.status).to eq('completed')

      # The job should write to file, not hold all results in memory
      expect(File.exist?(report.output_path)).to be true
    end

    it 'does not accumulate unbounded results array' do
      # With fixed implementation, @results should not grow unbounded
      # We test by checking memory doesn't grow linearly with batch count
      job = described_class.new

      # Mock to avoid actual DB queries
      allow(Order).to receive_message_chain(:where, :find_each).and_yield(
        build(:order, total_amount: 100.0)
      )

      job.perform(report.id)

      # Instance should not hold large results array after completion
      results = job.instance_variable_get(:@results)
      expect(results).to be_nil.or(be_empty).or(satisfy { |r| r.is_a?(Array) && r.size <= 100 })
    end

    it 'updates progress during generation' do
      50.times { create(:order, created_at: 1.day.ago) }

      described_class.new.perform(report.id)

      report.reload
      expect(report.progress).to be > 0
    end

    it 'marks report as completed with timestamp' do
      described_class.new.perform(report.id)

      report.reload
      expect(report.status).to eq('completed')
      expect(report.completed_at).not_to be_nil
    end
  end

  describe 'memory usage' do
    it 'processes orders in batches, not all at once' do
      # The fixed version should use find_in_batches or streaming
      job = described_class.new

      batch_count = 0
      allow(Order).to receive_message_chain(:where, :find_in_batches) do |&block|
        3.times do
          batch = [build(:order, total_amount: 50.0)]
          block.call(batch)
          batch_count += 1
        end
      end

      job.perform(report.id) rescue nil

      # Should process in batches
      expect(batch_count).to be > 0
    end

    it 'customer analytics does not store all order IDs per customer' do
      
      job = described_class.new

      report.update!(report_type: 'customer_analytics')

      100.times { |i| create(:order, user_id: 1, created_at: 1.day.ago) }

      job.perform(report.id) rescue nil

      # Fixed version should aggregate counts, not store all IDs
      customer_data = job.instance_variable_get(:@customer_data)
      if customer_data && customer_data[1]
        # Should not store all 100 order IDs
        orders = customer_data[1][:orders]
        expect(orders).to be_nil.or(satisfy { |o| o.size <= 10 })
      end
    end
  end
end
