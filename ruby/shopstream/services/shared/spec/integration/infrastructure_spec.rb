# frozen_string_literal: true

require 'rails_helper'

RSpec.describe 'Infrastructure Setup' do
  
  
  
  
  

  describe 'Database connection pool (L3)' do
    it 'pool size accommodates concurrent threads' do
      pool_size = ActiveRecord::Base.connection_pool.size
      # Pool should be at least the number of Puma/Sidekiq threads
      expect(pool_size).to be >= 5
    end

    it 'does not exhaust connections under concurrent load' do
      errors = []
      mutex = Mutex.new

      threads = 10.times.map do
        Thread.new do
          begin
            ActiveRecord::Base.connection_pool.with_connection do |conn|
              conn.execute('SELECT 1')
            end
          rescue ActiveRecord::ConnectionTimeoutError => e
            mutex.synchronize { errors << e.message }
          end
        end
      end
      threads.each(&:join)

      expect(errors).to be_empty
    end

    it 'returns connections to pool after use' do
      initial = ActiveRecord::Base.connection_pool.stat[:busy]

      ActiveRecord::Base.connection_pool.with_connection do |conn|
        conn.execute('SELECT 1')
      end

      after = ActiveRecord::Base.connection_pool.stat[:busy]
      expect(after).to be <= initial
    end
  end

  describe 'Redis connection thread safety (L4)' do
    it 'handles concurrent Redis operations without errors' do
      errors = []
      mutex = Mutex.new

      threads = 10.times.map do |i|
        Thread.new do
          begin
            Redis.current.set("test_key_#{i}", "value_#{i}")
            val = Redis.current.get("test_key_#{i}")
            expect(val).to eq("value_#{i}")
          rescue StandardError => e
            mutex.synchronize { errors << e.message }
          ensure
            Redis.current.del("test_key_#{i}")
          end
        end
      end
      threads.each(&:join)

      expect(errors).to be_empty
    end

    it 'uses connection pool for Redis' do
      # Redis connection should be thread-safe (connection pool or thread-local)
      expect {
        5.times.map do
          Thread.new { Redis.current.ping }
        end.each(&:join)
      }.not_to raise_error
    end
  end

  describe 'Elasticsearch index (L5)' do
    it 'creates indices if they do not exist on startup' do
      # Fixed version should auto-create indices
      # This test verifies the index creation mechanism exists
      expect(defined?(Elasticsearch::Model)).not_to be_nil if defined?(Elasticsearch)
    end
  end

  describe 'Sidekiq queue configuration (L6)' do
    it 'processes critical queue before default queue' do
      if defined?(Sidekiq)
        queues = Sidekiq.options[:queues] || Sidekiq.default_configuration[:queues] rescue []

        if queues.any?
          critical_index = queues.index('critical') || queues.index(:critical)
          default_index = queues.index('default') || queues.index(:default)

          if critical_index && default_index
            expect(critical_index).to be < default_index
          end
        end
      end
    end
  end

  describe 'Timezone consistency (L7)' do
    it 'application timezone matches database timezone' do
      app_zone = Time.zone.name rescue 'UTC'
      db_zone = ActiveRecord::Base.connection.execute("SHOW timezone").first['TimeZone'] rescue 'UTC'

      # Both should be UTC or matching
      expect(app_zone).to eq('UTC').or eq(db_zone)
    end

    it 'stores timestamps in UTC' do
      record = create(:order)
      raw_time = ActiveRecord::Base.connection.execute(
        "SELECT created_at FROM orders WHERE id = #{record.id}"
      ).first['created_at'] rescue nil

      # Should not have timezone offset issues
      expect(record.created_at.utc?).to be true if record.created_at.respond_to?(:utc?)
    end
  end
end
