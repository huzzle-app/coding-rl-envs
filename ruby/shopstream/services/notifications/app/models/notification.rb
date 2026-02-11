# frozen_string_literal: true

class Notification < ApplicationRecord
  validates :notification_type, presence: true
  validates :channel, presence: true
  validates :recipient, presence: true

  serialize :metadata, coder: JSON

  scope :pending, -> { where(status: 'pending') }
  scope :sent, -> { where(status: 'sent') }
  scope :delivered, -> { where(status: 'delivered') }
  scope :failed, -> { where(status: 'failed') }
  scope :scheduled, -> { where(status: 'scheduled') }
  scope :by_channel, ->(channel) { where(channel: channel) }
  scope :by_type, ->(type) { where(notification_type: type) }
  scope :for_user, ->(user_id) { where(user_id: user_id) }
  scope :ready_to_send, -> { where(status: 'pending').or(where(status: 'scheduled').where('scheduled_at <= ?', Time.current)) }

  def send!
    update!(status: 'sent', sent_at: Time.current)
  end

  def mark_delivered!
    update!(status: 'delivered', delivered_at: Time.current)
  end

  def mark_read!
    update!(status: 'read', read_at: Time.current)
  end

  def fail!(error_message:)
    update!(
      status: 'failed',
      error_message: error_message,
      retry_count: retry_count + 1
    )
  end

  def retry?
    status == 'failed' && retry_count < 3
  end

  def schedule!(at:)
    update!(status: 'scheduled', scheduled_at: at)
  end
end
