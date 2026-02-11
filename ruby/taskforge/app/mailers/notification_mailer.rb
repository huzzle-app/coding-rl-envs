# frozen_string_literal: true

class NotificationMailer < ApplicationMailer
  def notification_email(user_id, notification_id)
    @user = User.find(user_id)
    @notification = Notification.find(notification_id)

    mail(
      to: @user.email,
      subject: 'TaskForge Notification'
    )
  end
end
