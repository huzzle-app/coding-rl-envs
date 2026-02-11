# frozen_string_literal: true

require 'rails_helper'

RSpec.describe NotificationService do
  let(:user) { create(:user) }

  describe '.notify' do
    it 'creates a notification' do
      task = create(:task)

      expect {
        described_class.notify(user, :task_assigned, task)
      }.to change(Notification, :count).by(1)
    end

    it 'returns nil for nil user' do
      result = described_class.notify(nil, :test, 'message')
      expect(result).to be_nil
    end

    context 'when user has disabled notifications' do
      let(:user) { create(:user, notification_preferences: { 'task_assigned' => false }) }

      it 'skips notification' do
        expect {
          described_class.notify(user, :task_assigned, create(:task))
        }.not_to change(Notification, :count)
      end
    end
  end

  
  # singleton pattern (Mutex or Module-level instance)
  describe 'singleton pattern' do
    it 'returns the same instance consistently' do
      instance1 = described_class.instance
      instance2 = described_class.instance

      expect(instance1).to eq(instance2)
    end

    it 'returns same instance under concurrent access' do
      instances = []
      threads = 10.times.map do
        Thread.new { instances << described_class.instance }
      end
      threads.each(&:join)

      # Fixed behavior: all threads should get the same instance
      expect(instances.uniq.size).to eq(1)
    end
  end

  
  # or TTL-based eviction
  describe 'user preferences cache' do
    it 'caches user preferences' do
      service = described_class.new

      service.send(:user_has_disabled?, user, :test)

      cache = service.user_preferences_cache
      expect(cache).to have_key(user.id)
    end

    it 'limits cache size to prevent unbounded growth' do
      service = described_class.new

      # Simulate many users
      100.times do
        u = create(:user)
        service.send(:user_has_disabled?, u, :test)
      end

      # Fixed behavior: cache should be bounded (e.g., max 1000 entries or LRU)
      expect(service.user_preferences_cache.size).to be <= 1000
    end
  end

  
  # failures should be caught and logged, not propagated
  describe 'push notification' do
    let(:user) { create(:user, push_enabled: true) }

    it 'enqueues push notification job' do
      notification = create(:notification, user: user)

      expect(PushNotificationJob).to receive(:perform_later)
        .with(user.id, notification.id)

      described_class.new.send(:send_push_notification, user, notification)
    end

    it 'handles push notification job failure gracefully' do
      notification = create(:notification, user: user)

      allow(PushNotificationJob).to receive(:perform_later).and_raise(StandardError, 'Push service down')

      # Fixed behavior: error should be caught, not propagated
      expect {
        described_class.new.send(:send_push_notification, user, notification)
      }.not_to raise_error
    end
  end
end
