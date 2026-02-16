# frozen_string_literal: true

require 'rails_helper'

RSpec.describe 'Callback Lifecycle Bugs' do
  
  

  describe 'Validation side effects (C3)' do
    it 'validation callbacks do not trigger external side effects' do
      external_calls = 0
      allow(InventoryService).to receive(:check_stock) { external_calls += 1; true }

      order = build(:order)

      # Calling valid? should NOT trigger external service calls
      order.valid?

      expect(external_calls).to eq(0)
    end

    it 'validation does not modify other records' do
      order = build(:order)
      initial_count = AuditLog.count rescue 0

      order.valid?

      # Validation should not create audit log entries
      expect(AuditLog.count).to eq(initial_count)
    end
  end

  describe 'Notification on failed transaction (C6)' do
    it 'does not send notifications when transaction rolls back' do
      notification_count = 0
      allow(NotificationService).to receive(:notify) { notification_count += 1 }

      begin
        ActiveRecord::Base.transaction do
          order = create(:order)
          order.update!(status: 'confirmed')
          raise ActiveRecord::Rollback
        end
      rescue StandardError
        nil
      end

      # Notification should not be sent since transaction was rolled back
      expect(notification_count).to eq(0)
    end

    it 'sends notification only after transaction commits' do
      notification_count = 0
      allow(NotificationService).to receive(:notify) { notification_count += 1 }

      ActiveRecord::Base.transaction do
        order = create(:order)
        order.update!(status: 'confirmed')
      end

      # Notification should be sent after commit
      expect(notification_count).to be >= 1
    end
  end
end
