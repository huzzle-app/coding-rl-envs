# frozen_string_literal: true

class Mention < ApplicationRecord
  belongs_to :comment
  belongs_to :user

  validates :comment_id, uniqueness: { scope: :user_id }

  after_create :notify_user

  private

  def notify_user
    Notification.create!(
      user: user,
      notification_type: 'mention',
      message: "You were mentioned in a comment",
      notifiable: comment
    )
  end
end
