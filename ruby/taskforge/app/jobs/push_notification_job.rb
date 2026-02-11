# frozen_string_literal: true

class PushNotificationJob < ApplicationJob
  queue_as :push_notifications

  def perform(user_id, notification_id)
    user = User.find(user_id)
    notification = Notification.find(notification_id)

    # In a real app, this would send to a push service
    Rails.logger.info("Sending push notification to user #{user_id}: #{notification.message}")
  rescue ActiveRecord::RecordNotFound
    # User or notification was deleted, ignore
  end
end
