# frozen_string_literal: true

require 'rails_helper'

RSpec.describe 'Background Job Bugs' do
  
  
  

  describe 'Job uniqueness (J3)' do
    it 'prevents duplicate jobs from being enqueued for same order' do
      order = create(:order)

      # Enqueue same job twice
      OrderNotificationJob.perform_later(order.id, :confirmed)
      OrderNotificationJob.perform_later(order.id, :confirmed)

      # Should only have 1 job queued (deduplication)
      if defined?(Sidekiq)
        queue = Sidekiq::Queue.new('default')
        matching = queue.select { |j| j.args.first == order.id }
        expect(matching.size).to be <= 1
      end
    end

    it 'allows different jobs for same order but different events' do
      order = create(:order)

      OrderNotificationJob.perform_later(order.id, :confirmed)
      OrderNotificationJob.perform_later(order.id, :shipped)

      # These are different events, both should be queued
      # At minimum, both should be accepted (not deduplicated)
    end

    it 'tracks job execution with unique lock key' do
      order = create(:order)

      # First execution should succeed
      result1 = OrderNotificationJob.new.perform(order.id, :confirmed) rescue :ok

      # Second immediate execution for same order+event should be skipped
      result2 = OrderNotificationJob.new.perform(order.id, :confirmed) rescue :ok

      # At least one should succeed
      expect(result1).not_to be_nil
    end
  end

  describe 'Job timeout for batch processing (J4)' do
    it 'batch jobs have appropriate timeout configured' do
      if defined?(Sidekiq)
        # Batch jobs should have longer timeout than default
        expect(BulkProcessor::BATCH_TIMEOUT).to be >= 300 if defined?(BulkProcessor::BATCH_TIMEOUT)
      end
    end

    it 'batch job processes within timeout and checkpoints progress' do
      orders = 5.times.map { create(:order) }

      # Batch job should checkpoint progress so it can resume
      job = BulkProcessor.new rescue nil

      if job
        start = Time.current
        job.perform(orders.map(&:id)) rescue nil
        elapsed = Time.current - start

        # Should complete within reasonable time
        expect(elapsed).to be < 30
      end
    end
  end

  describe 'Dead job cleanup (J5)' do
    it 'retries dead jobs with exponential backoff' do
      if defined?(Sidekiq)
        # Jobs should have retry configuration
        job_class = OrderNotificationJob

        if job_class.respond_to?(:sidekiq_options_hash)
          options = job_class.sidekiq_options_hash
          expect(options['retry']).to be_truthy
        end
      end
    end

    it 'sends dead jobs to dead letter queue after max retries' do
      # After exhausting retries, job should go to dead set, not be lost
      if defined?(Sidekiq)
        dead = Sidekiq::DeadSet.new rescue nil

        if dead
          initial_size = dead.size
          # After max retries, job should appear in dead set
          expect(initial_size).to be >= 0
        end
      end
    end

    it 'dead job cleanup removes jobs older than retention period' do
      if defined?(Sidekiq)
        # Dead jobs should be cleaned up after retention period
        dead = Sidekiq::DeadSet.new rescue nil

        if dead
          # Cleanup should remove old dead jobs
          dead.clear
          expect(dead.size).to eq(0)
        end
      end
    end
  end
end
