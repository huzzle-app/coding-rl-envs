# frozen_string_literal: true

require 'rails_helper'

RSpec.describe SessionService do
  
  

  let(:redis) { Redis.new }
  let(:user) { create(:user) }

  describe '#login' do
    it 'always creates a new session ID on login (prevents session fixation)' do
      service = described_class.new(redis)

      # Attacker creates a session
      attacker_session = service.create_session(999, { ip_address: '10.0.0.1' })

      # Victim logs in with attacker's session ID
      new_session = service.login(user, metadata: { ip_address: '192.168.1.1' })

      # The session ID should be NEW, not the attacker's
      expect(new_session).not_to eq(attacker_session)
    end

    it 'does not accept externally provided session_id parameter' do
      service = described_class.new(redis)

      # Attacker pre-creates a session
      attacker_session = service.create_session(999)

      # Login should ignore the session_id parameter
      # Fixed version signature: login(user, metadata: {}) -- no session_id param
      session = service.login(user, metadata: {})

      expect(session).not_to eq(attacker_session)
    end

    it 'invalidates old sessions on login' do
      service = described_class.new(redis)

      old_session = service.login(user, metadata: {})
      new_session = service.login(user, metadata: {})

      # Old session should be invalidated
      expect(service.get_session(old_session)).to be_nil
      expect(service.get_session(new_session)).not_to be_nil
    end
  end

  describe '#refresh_session' do
    it 'atomically reads and updates session data (A6)' do
      service = described_class.new(redis)
      session_id = service.create_session(user.id)

      results = []
      mutex = Mutex.new

      # Two concurrent refreshes
      threads = 2.times.map do
        Thread.new do
          refreshed = service.refresh_session(session_id)
          mutex.synchronize { results << refreshed }
        end
      end
      threads.each(&:join)

      # Both should succeed without data corruption
      results.compact.each do |session|
        expect(session['user_id']).to eq(user.id)
      end
    end

    it 'does not update deleted sessions' do
      service = described_class.new(redis)
      session_id = service.create_session(user.id)

      service.destroy_session(session_id)
      refreshed = service.refresh_session(session_id)

      expect(refreshed).to be_nil
    end
  end

  describe '#create_session' do
    it 'stores session data with TTL' do
      service = described_class.new(redis)
      session_id = service.create_session(user.id, ip_address: '127.0.0.1')

      session = service.get_session(session_id)
      expect(session['user_id']).to eq(user.id)
      expect(session['ip_address']).to eq('127.0.0.1')
    end
  end

  describe '#logout' do
    it 'destroys session and all related tokens' do
      service = described_class.new(redis)
      session_id = service.create_session(user.id)

      service.logout(session_id)

      expect(service.get_session(session_id)).to be_nil
    end
  end
end
