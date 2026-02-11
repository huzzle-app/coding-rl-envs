# frozen_string_literal: true

class NotificationService
  
  @@instance = nil

  def self.instance
    @@instance ||= new
  end

  def self.notify(user, event_type, subject)
    instance.send_notification(user, event_type, subject)
  end

  def self.notify_admins(message)
    User.admins.find_each do |admin|
      instance.send_notification(admin, :admin_alert, message)
    end
  end

  def send_notification(user, event_type, subject)
    return if user.nil?
    return if user_has_disabled?(user, event_type)

    notification = create_notification(user, event_type, subject)

    
    send_push_notification(user, notification)
    send_email_notification(user, notification)

    notification
  end

  def user_preferences_cache
    @user_preferences_cache ||= {}
  end

  private

  def create_notification(user, event_type, subject)
    Notification.create!(
      user: user,
      notification_type: event_type,
      notifiable: subject.is_a?(String) ? nil : subject,
      message: build_message(event_type, subject)
    )
  end

  def build_message(event_type, subject)
    case event_type
    when :task_assigned
      "You have been assigned to task: #{subject.title}"
    when :mentioned
      "You were mentioned in a comment"
    when :project_completed
      "Project #{subject.name} has been completed"
    else
      "You have a new notification"
    end
  end

  def user_has_disabled?(user, event_type)
    
    user_preferences_cache[user.id] ||= user.notification_preferences || {}
    user_preferences_cache[user.id][event_type.to_s] == false
  end

  def send_push_notification(user, notification)
    return unless user.push_enabled?

    
    PushNotificationJob.perform_later(user.id, notification.id)
  end

  def send_email_notification(user, notification)
    return unless user.email_notifications_enabled?

    
    NotificationMailer.notification_email(user.id, notification.id).deliver_later
  end
end
