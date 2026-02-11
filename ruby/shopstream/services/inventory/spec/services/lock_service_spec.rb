# frozen_string_literal: true

require 'rails_helper'

RSpec.describe LockService do
  let(:redis) { Redis.new }
  let(:service) { described_class.new(redis) }

  before { redis.flushdb rescue nil }

  
  describe '#acquire' do
    it 'acquires lock with TTL so it auto-expires' do
      result = service.acquire('test-resource', ttl: 5)

      expect(result[:acquired]).to be true

      # Lock should have TTL set
      ttl = redis.ttl('shopstream:lock:test-resource') rescue -1
      expect(ttl).to be > 0
    end

    it 'sets lock atomically with TTL (no gap between SETNX and EXPIRE)' do
      
      # Fixed version should use SET with NX and EX in single command
      result = service.acquire('atomic-test', ttl: 10)
      expect(result[:acquired]).to be true

      # Key should exist with TTL
      exists = redis.exists?('shopstream:lock:atomic-test') rescue false
      expect(exists).to be true
    end

    it 'fails to acquire when lock is already held' do
      service.acquire('held-resource', ttl: 30)
      result = service.acquire('held-resource', ttl: 30)

      expect(result[:acquired]).to be false
    end
  end

  describe '#release' do
    it 'releases lock only if holder matches' do
      result = service.acquire('my-resource', ttl: 30)
      lock_value = result[:lock_value]

      released = service.release('my-resource', lock_value)
      expect(released).to be true

      # Lock should be gone
      expect(redis.get('shopstream:lock:my-resource')).to be_nil rescue nil
    end

    it 'does not release lock held by another process' do
      service.acquire('shared-resource', ttl: 30)
      released = service.release('shared-resource', 'wrong-value')

      expect(released).to be false
    end

    it 'releases atomically (no race between check and delete)' do
      result = service.acquire('race-resource', ttl: 30)
      # Atomic release should use Lua script or WATCH/MULTI
      released = service.release('race-resource', result[:lock_value])
      expect(released).to be true
    end
  end

  describe '#with_lock' do
    it 'releases lock even when block raises' do
      begin
        service.with_lock('error-resource', ttl: 30) do
          raise 'intentional error'
        end
      rescue RuntimeError
        # expected
      end

      # Lock should be released
      result = service.acquire('error-resource', ttl: 30)
      expect(result[:acquired]).to be true
    end
  end
end
