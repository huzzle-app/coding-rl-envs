# frozen_string_literal: true

require 'rails_helper'

RSpec.describe OrderNotificationJob do
  
  let(:order) { create(:order, :with_user) }

  describe '#perform' do
    it 'does not send duplicate notifications on retry' do
      email_count = 0
      allow(OrderMailer).to receive_message_chain(:confirmation, :deliver_now) { email_count += 1 }
      allow(SmsService).to receive(:send)
      allow(PushService).to receive(:send)
      allow(NotificationLog).to receive(:create!)

      # First execution
      described_class.new.perform(order.id, :confirmed) rescue nil

      # Simulate retry (second execution with same args)
      described_class.new.perform(order.id, :confirmed) rescue nil

      # Fixed version should send email only once
      expect(email_count).to eq(1)
    end

    it 'does not trigger duplicate refunds on cancellation retry' do
      refund_count = 0
      allow(OrderMailer).to receive_message_chain(:cancelled, :deliver_now)
      allow(RefundService).to receive_message_chain(:new, :process_refund) { refund_count += 1 }
      allow(NotificationLog).to receive(:create!)

      described_class.new.perform(order.id, :cancelled) rescue nil
      described_class.new.perform(order.id, :cancelled) rescue nil

      # Should only refund once
      expect(refund_count).to eq(1)
    end

    it 'logs notification after successful send' do
      allow(OrderMailer).to receive_message_chain(:confirmation, :deliver_now)
      allow(SmsService).to receive(:send)
      allow(PushService).to receive(:send)

      expect(NotificationLog).to receive(:create!).with(
        hash_including(order_id: order.id, notification_type: :confirmed)
      )

      described_class.new.perform(order.id, :confirmed) rescue nil
    end
  end
end
